# api.py

# todo: convert dependicies
# utils = require('projects/GLANCE:ccdcUtilities/api')
import sys
import os

from ee import collection, imagecollection

container_folder = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..'
))
sys.path.insert(0, container_folder)
import ee
from coded_python.ccdc import ccdc
from coded_python.ccdc import classification
from coded_python.image_collections import simple_cols as cs
from coded_python.params import classParams, changeDetectionParams, generalParams

ee.Initialize()

# todo: implement custom ndfi 
class parameters:
    def __init__(self):
        self.endmembers = {
            'gv': [.0500, .0900, .0400, .6100, .3000, .1000],
            'shade': [0, 0, 0, 0, 0, 0],
            'npv': [.1400, .1700, .2200, .3000, .5500, .3000],
            'soil': [.2000, .3000, .3400, .5800, .6000, .5800],
            'cloud': [.9000, .9600, .8000, .7800, .7200, .6500],
        }
        self.cloudThreshold = 0.1


PARAMTERS = parameters()

# deprecated probally wont need...


def unmix(image: ee.Image, endmembers: dict = None, cloudThreshold: float = None) -> ee.Image:
    '''
    * Spectral unmixing using endmembers from Souza et al., 2005
    * @param {ee.Image}  image  surface reflectance image with 6 bands (i.e. not thermal)
    * @param {object}  endmembers   spectral endmembers in units reflectance
    * @param {float}  cloudThreshold  threshold to mask based on cloud fraction 
    * @returns {ee.Image} Image fractions and NDFI
    '''
    # todo, what bands? 1-7 dont include thermal... prob 2-7
    if endmembers is None:
        endmembers = PARAMTERS.endmembers
    if cloudThreshold is None:
        cloudThreshold = PARAMTERS.cloudThreshold

    cfThreshold = ee.Image.constant(cloudThreshold)

    unmixImage = image.unmix(
        [endmembers['gv'], endmembers['shade'], endmembers['npv'], endmembers['soil'], endmembers['cloud']], True, True).rename(['band_0', 'band_1', 'band_2', 'band_3', 'band_4'])

    imageWithFractions = image.geoaddBands(unmixImage)

    cloudMask = imageWithFractions.select('band_4').lt(cfThreshold)

    ndfi = unmixImage.expression(
        '((GV / (1 - SHADE)) - (NPV + SOIL)) / ((GV / (1 - SHADE)) + NPV + SOIL)', {
            'GV': unmixImage.select('band_0'),
            'SHADE': unmixImage.select('band_1'),
            'NPV': unmixImage.select('band_2'),
            'SOIL': unmixImage.select('band_3')})

    return imageWithFractions.addBands(ndfi.rename(['NDFI'])) \
        .select(['band_0', 'band_1', 'band_2', 'band_3', 'NDFI']) \
        .rename(['GV', 'Shade', 'NPV', 'Soil', 'NDFI']) \
        .updateMask(cloudMask)

def make_class_params(generalParams):
    # // Classification Parameter
    # TODO: clean this and ccdc.classifySegments up so None properties can be removed from dict.
    classParams = {
        'imageToClassify': None,
        'numberOfSegments': len(generalParams['segs']),
        'bandNames':  generalParams['classBands'],
        'ancillary': None,
        'ancillaryFeatures': None,
        'trainingData': None,
        'classifier': ee.Classifier.smileRandomForest(150),
        'studyArea': generalParams['studyArea'],
        'classProperty': 'landcover',#TODO: this is the prop used for training classifier, should be parameter
        'coefs': ['INTP', 'SIN', 'COS', 'RMSE'],
        'trainProp': None,
        'seed': None,
        'subsetTraining': False,
    }
    return classParams

# functionection used by coded
def make_general_params(params: dict):
    generalParams = {
        'segs': params.get('segs', ['S1', 'S2', 'S3', 'S4', 'S5']),
        # TODO default -> utils.Inputs.getLandsat().filterBounds(generalParams.studyArea).first().bandNames().getInfo()
        'classBands': params.get('classBands', ['GV', 'Shade', 'NPV', 'Soil', 'NDFI']),
        'coefs': params.get('coefs', ['INTP', 'SIN', 'COS', 'RMSE', 'SLP']),
        'forestValue': params.get('forestValue', 1),
        # TODO default ->  ee.Geometry(Map.getBounds(true))
        'studyArea': params.get('studyArea', None),
        'mask': params.get('forestMask', None),
        'startYear': params.get('startYear', None),
        'endYear': params.get('endYear', None),
    }
    return generalParams
def make_general_params_v2(params: dict, change_params : changeDetectionParams):
    # todo: test params.collection.ee function works
    if params.get('startYear', None) is None:
        start_year = changeDetectionParams.collection.aggregate_min(
        'year')
    if params.get('endYear', None) is None:
        end_year = changeDetectionParams.collection.aggregate_max(
            'year')
        
    general_params = {
        'segs': params.get('segs', ['S1', 'S2', 'S3', 'S4', 'S5']),
        
        # TODO default -> utils.Inputs.getLandsat().filterBounds(generalParams.studyArea).first().bandNames().getInfo()
        'classBands': params.get('classBands', ['GV', 'Shade', 'NPV', 'Soil', 'NDFI']),
        
        'coefs': params.get('coefs', ['INTP', 'SIN', 'COS', 'RMSE', 'SLP']),
        'forestValue': params.get('forestValue', 1),
        
        # TODO default ->  ee.Geometry(Map.getBounds(true))
        'studyArea': params.get('studyArea', None),
        
        'mask': params.get('forestMask', None),
        'startYear': start_year,
        'endYear': end_year,
    }
    return generalParams(general_params)


def make_change_detection_params(params: dict, **kwargs):
    # // CODED Change Detection Parameters
    changeDetectionParams = {
        'collection': params.get('collection', cs.getLandsat(**kwargs)),
        'lambda': params.get('lambda', 20/10000),
        'minNumOfYearsScaler': params.get('minNumOfYearsScaler', 1.33),
        'dateFormat': 1,
        'minObservations': params.get('minObservations', 3),
        'chiSquareProbability': params.get('chiSquareProbability', .9),
        # 'breakpointBands': params.get('breakpointBands', ['NDFI']), #TODO: ask eric about why this is here?
    }
    return changeDetectionParams


def make_output_dict_v2(changeDetectionParams: changeDetectionParams, generalParams: generalParams):
    # // Output Dictionary
    output = {
        'Change_Parameters': changeDetectionParams.dict(),
        'General_Parameters': generalParams.dict(),
        'Layers': {
            'rawChangeOutput': None,
            'formattedChangeOutput': None,
            'mask': None},
    }
    return output

def make_output_dict(changeDetectionParams: dict, generalParams: dict):
    # // Output Dictionary
    output = {
        'Change_Parameters': changeDetectionParams,
        'General_Parameters': generalParams,
        'Layers': {
            'rawChangeOutput': None,
            'formattedChangeOutput': None,
            'mask': None},
    }
    return output
# prep input collection - filter dates, set band names, add year img


def prep_collection(changeDetectionParams: dict, generalParams: dict):
    changeDetectionParams['collection'] = changeDetectionParams['collection'] \
        .filterBounds(generalParams['studyArea']).select(generalParams['classBands']) \
        .map(lambda i: i.set('year', i.date().get('year')))

def prep_collection_v2(change: changeDetectionParams, general: generalParams):
    change.collection = change.collection \
        .filterBounds(general.studyArea).select(general.classBands) \
        .map(lambda i: i.set('year', i.date().get('year')))


def run_ccdc(output: dict, changeDetectionParams: dict):
    #   // Run CCDC/CODED
    output['Layers']['rawChangeOutput'] = ee.Algorithms.TemporalSegmentation.Ccdc(
        **changeDetectionParams)
def run_ccdc_v2(output: dict, change:changeDetectionParams):
    #   // Run CCDC/CODED
    output['Layers']['rawChangeOutput'] = ee.Algorithms.TemporalSegmentation.Ccdc(
        **{'collection': change.collection,
        'minNumOfYearsScaler' : change.minNumOfYearsScaler, 
        'dateFormat' : change.dateFormat,
        'minObservations' : change.minObservations,
        'chiSquareProbability' : change.chiSquareProbability,
        'lambda' : change._lambda})
        # change.dict_ee())


def build_ccdc_image(output: dict, generalParams: dict):
    output['Layers']['formattedChangeOutput'] = ccdc.buildCcdImage(output['Layers']['rawChangeOutput'],
                                                                   len(generalParams['segs']), generalParams['classBands'])

def build_ccdc_image_v2(output: dict, general : generalParams):
    output['Layers']['formattedChangeOutput'] = ccdc.buildCcdImage(output['Layers']['rawChangeOutput'],
                                                                   len(general.segs), general.classBands)

def prep_samples(samples:ee.FeatureCollection, output:dict, generalParams:dict)-> ee.FeatureCollection:
    """ prepares sample collection by adding ccdc coefs from the formatted change output"""
    # // Get training data coefficients
    def prep_sample(feat: ee.Feature) -> ee.Feature:
        coefsForTraining = ccdc.getMultiCoefs(output['Layers']['formattedChangeOutput'], ee.Image.constant(feat.getNumber('year')),
                                            generalParams['classBands'], generalParams['coefs'], True, generalParams['segs'], 'before')

        sampleForTraining = feat.setMulti(coefsForTraining.reduceRegion(**{
            'geometry': feat.geometry(),
            'scale': 90,
            'reducer': ee.Reducer.mean()
        }))

        return sampleForTraining
    
    return samples.map(prep_sample)

def run_classification(output,generalParams,classParams):
    #TODO : anywhere NDFI is string maybe replace w breakpoint_bands?
    # // Run classification
    # note: stopping here, need to pythonify utils classification classifysegments and find py equlievent of apply()
    # note: should be able to pass classParams into function.
    output['Layers']['classificationRaw'] = classification.classifySegments(**classParams)

    # think about when this should be run, TODO: where is there another mask check here?? see mask check before prep_samples
    if output['Layers']['mask'] is None:
        output['Layers']['mask'] = output['Layers']['classificationRaw'].select(0).eq(generalParams['forestValue'])

    tMags = output['Layers']['formattedChangeOutput'].select('.*NDFI_MAG').lt(0) \
        .select(ee.List.sequence(0, len(generalParams['segs']) - 2)) 
    factor = ee.Image(1).addBands(tMags)
    output['Layers']['classificationRaw'] = output['Layers']['classificationRaw'].multiply(factor).selfMask()

    output['Layers']['classification'] = output['Layers']['classificationRaw'] \
        .select(ee.List.sequence(1, len(generalParams['segs']) - 1)) \
        .int8()

    output['Layers']['classification'] = output['Layers']['classification'].updateMask(output['Layers']['mask'])
    output['Layers']['magnitude'] = output['Layers']['formattedChangeOutput'].select('.*NDFI_MAG')

def run_classification_v2(output:dict,general: generalParams, classp :classParams):
    #TODO : anywhere NDFI is string maybe replace w breakpoint_bands?
    # // Run classification
    # note: stopping here, need to pythonify utils classification classifysegments and find py equlievent of apply()
    # note: should be able to pass classParams into function.
    output['Layers']['classificationRaw'] = classification.classifySegments(numberOfSegments=classp.numberOfSegments,
        bandNames=classp.bandNames,
        ancillary=classp.ancillary,
        ancillaryFeatures=classp.ancillaryFeatures,
        trainingData=classp.trainingData,
        classifier=classp.classifier,
        classProperty=classp.classProperty,
        coefs=classp.coefs,
        seed=classp.seed,
        subsetTraining=classp.subsetTraining,
        studyArea= classp.studyArea,
        trainProp=classp.trainProp,
        imageToClassify=classp.imageToClassify
    )

    # think about when this should be run, TODO: where is there another mask check here?? see mask check before prep_samples
    if output['Layers']['mask'] is None:
        output['Layers']['mask'] = output['Layers']['classificationRaw'].select(0).eq(general.forestValue)

    tMags = output['Layers']['formattedChangeOutput'].select('.*NDFI_MAG').lt(0) \
        .select(ee.List.sequence(0, len(general.segs) - 2)) 
    
    factor = ee.Image(1).addBands(tMags)
    output['Layers']['classificationRaw'] = output['Layers']['classificationRaw'].multiply(factor).selfMask()

    output['Layers']['classification'] = output['Layers']['classificationRaw'] \
        .select(ee.List.sequence(1, len(general.segs) - 1)) \
        .int8()

    output['Layers']['classification'] = output['Layers']['classification'].updateMask(output['Layers']['mask'])
    output['Layers']['magnitude'] = output['Layers']['formattedChangeOutput'].select('.*NDFI_MAG')

def degradation_and_deforestation(output,generalParams):
    deg = output['Layers']['classificationStudyPeriod'].eq(generalParams['forestValue']).reduce(ee.Reducer.max()).rename('Degradation')
    defor = output['Layers']['classificationStudyPeriod'].neq(generalParams['forestValue']).reduce(ee.Reducer.max()).rename('Deforestation')
    both = deg.And(defor)
    return deg, defor, both

def tbreaks(output, generalParams):
    tBreaks = output['Layers']['formattedChangeOutput'].select('.*tBreak').select(ee.List.sequence(0, len(generalParams['segs']) - 2))
    tBreaksInterval = tBreaks.floor().gte(ee.Number(generalParams['startYear'])).And(tBreaks.floor().lte(ee.Number(generalParams['endYear'])))

    return tBreaks, tBreaksInterval

def make_degradation_and_deforestation(output, generalParams):
    tBreaks, tBreaksInterval = tbreaks(output, generalParams)
    output['Layers']['classificationStudyPeriod'] =  output['Layers']['classification'].updateMask(tBreaksInterval)
    deg, defor, both = degradation_and_deforestation(output, generalParams)

    output['Layers']['Degradation'] = deg.And(both.Not()).selfMask().int8()
    output['Layers']['Deforestation'] = defor.And(both.Not()).selfMask().int8()
    output['Layers']['Both'] = both.selfMask().int8()
    # note from   classificationStudyPeriod to both all return errors if some data are missing values...
    # some how when we get to the end it works though, so is this needed?
    dateOfDegradation = output['Layers']['classificationStudyPeriod'] \
        .eq(generalParams['forestValue']) \
        .multiply(tBreaks) \
        .multiply(tBreaksInterval)
    
    dateOfDeforestation = output['Layers']['classificationStudyPeriod'] \
        .neq(generalParams['forestValue']) \
        .multiply(tBreaks) \
        .multiply(tBreaksInterval)

    output['Layers']['DatesOfDegradation'] = dateOfDegradation
    output['Layers']['DatesOfDeforestation'] = dateOfDeforestation

def make_stratification(output):
    # // Make single layer stratification
    stratification = output['Layers']['mask'].remap([0,1],[2,1]) \
        .where(output['Layers']['Degradation'], 3) \
        .where(output['Layers']['Deforestation'], 4) \
        .where(output['Layers']['Both'], 5)

    output['Layers']['Stratification'] = stratification.rename('stratification').int8()


def coded_v2(input_gen_params: dict, input_change_params:dict, input_class_params:dict):
    change_params = changeDetectionParams(**input_change_params)
    # step 2  make general params
    general_params = generalParams(**input_gen_params)
    # check if start and end year are input
    if general_params.startYear is None:
        general_params.startYear = change_params.get_start_end_from_col('start')
    if general_params.endYear is None:
        general_params.endYear = change_params.get_start_end_from_col('end')
    
    output = make_output_dict_v2(change_params, general_params)
    prep_collection_v2(change_params, general_params)
    run_ccdc_v2(output, change_params)
    build_ccdc_image_v2(output, general_params)

    # make classification params
    image_to_classify = output['Layers']['formattedChangeOutput']
    class_params = classParams(**input_class_params,
        imageToClassify=image_to_classify,
        bandNames=general_params.classBands,
        studyArea=general_params.studyArea,
        numberOfSegments=len(general_params.segs)
        )
    if class_params.prepTraining:
        class_params.trainingData = class_params.prep_samples(general_params)

    run_classification_v2(output,general_params,class_params)
    return output

def coded(params: dict):
    '''CODED algorithm

    Args:
        params (dict): Parameter dictionary that contains the key-word arguments below
            start (str): start date to filter image collection by e.g. "2018-01-01"
            end (str): end date to filter image collection by e.g. "2020-12-31"
            prepTraining (bool): boolean argument to generate, sample, and export coefficients for training data (make CODED run faster) 
            studyarea (ee.FeatureCollection): The study area.
            training (ee.FeatureCollection): Training points that include a forest value and 'year' property for sampling coefficients
            forestValue (int): The value of forest in the input mask 
            classBands (list): class band def: default ['NDFI', 'GV', 'Shade', 'NPV', 'Soil']
            breakpointBands (list): ????
            startYear (int): CODED start year
            endYear (int): CODED end year
    Returns:
        [type]: [description]
    '''
    if params is None:
        return 'Missing parameter object'

    generalParams = make_general_params(params)
    # // CODED Change Detection Parameters
    changeDetectionParams = make_change_detection_params(
        params, region=generalParams['studyArea'], start=params['start'], end=params['end'])
    # Class parameter dictionary 
    classParams = make_class_params(generalParams)
    # // Output Dictionary
    output = make_output_dict(changeDetectionParams, generalParams)

    # TODO: Ask Eric about this. reads like input is a binary mask, then uses forest value to define mask again. big chance for errors here
    # if params['forestMask']:
    #     output.Layers['mask'] = params.forestMask.eq(params.forestValue)
    # alt while this is dev. mask should be required input imo and can be added without if/else
    # if params['forestMask']:
    #     output.Layers['mask'] = params.forestMask
    # # dev delete later
    # else:
    #     output.Layers['mask'] = ee.Image(1)
    prep_collection(changeDetectionParams, generalParams)

    #
    if generalParams['startYear'] is None:
        generalParams['startYear'] = changeDetectionParams['collection'].aggregate_min(
            'year')
    if generalParams['endYear'] is None:
        generalParams['endYear'] = changeDetectionParams['collection'].aggregate_max(
            'year')
    #   // ----------------- Run Analysis
    run_ccdc(output, changeDetectionParams)
    build_ccdc_image(output, generalParams)
    #  Format classification parameters and extract values
    prep = params.get('prepTraining', False)

    if prep:
        classParams['trainingData'] = prep_samples(params.get('training'), output, generalParams)
        # TODO how to handel exporting table? do we even want prep training in sepal? prob
        return classParams['trainingData']
    else:
        classParams['trainingData'] = params.get('training')
    # TODO: note, should prep exit or try to continue?
    classParams['imageToClassify'] = output['Layers']['formattedChangeOutput']

    run_classification(output,generalParams,classParams)
    # // ----------------- Post-process
    make_degradation_and_deforestation(output, generalParams)
    make_stratification(output)

    return   output

