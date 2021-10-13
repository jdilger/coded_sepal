# api.py

# todo: convert dependicies
# utils = require('projects/GLANCE:ccdcUtilities/api')
import sys
import os
from rich import print

container_folder = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..'
))
sys.path.insert(0, container_folder)
import ee
from coded_python.ccdc import ccdc
from coded_python.image_collections import simple_cols as cs
from coded_python.utils import exporting

ee.Initialize()


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
    classParams = {
        'imageToClassify': None,
        'numberOfSegments': len(generalParams['segs']),
        'bandNames':  generalParams['classBands'],
        'ancillary': None,
        'ancillaryFeatures': None,
        'trainingData': None,
        'classifier': ee.Classifier.smileRandomForest(150),
        'studyArea': generalParams['studyArea'],
        'classProperty': 'landcover',
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


def make_change_detection_params(params: dict, **kwargs):
    # // CODED Change Detection Parameters
    changeDetectionParams = {
        'collection': params.get('collection', cs.getLandsat(**kwargs)),
        'lambda': params.get('lambda', 20/10000),
        'minNumOfYearsScaler': params.get('minNumOfYearsScaler', 1.33),
        'dateFormat': 1,
        'minObservations': params.get('minObservations', 3),
        'chiSquareProbability': params.get('chiSquareProbability', .9),
        'breakpointBands': params.get('breakpointBands', ['NDFI']),
    }
    return changeDetectionParams


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


def run_ccdc(output: dict, changeDetectionParams: dict):
    #   // Run CCDC/CODED
    output['Layers']['rawChangeOutput'] = ee.Algorithms.TemporalSegmentation.Ccdc(
        **changeDetectionParams)


def build_ccdc_image(output: dict, generalParams: dict):
    output['Layers']['formattedChangeOutput'] = ccdc.buildCcdImage(output['Layers']['rawChangeOutput'],
                                                                   len(generalParams['segs']), generalParams['classBands'])

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

def coded(params: dict):
    if params is None:
        return 'Missing parameter object'

    generalParams = make_general_params(params)

    # // CODED Change Detection Parameters

    changeDetectionParams = make_change_detection_params(
        params, region=generalParams['studyArea'], start=params['start'], end=params['end'])

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
        # description = 'python-js-ccdc'
        # assetid = 'projects/python-coded/assets/tests/prepped/python_prepped_samples'
        # exporting.export_table_asset(collection,description,assetid)
        return classParams['trainingData']

    else:
        classParams['trainingData'] = params.get('training')

    classParams['imageToClassify'] = output['Layers']['formattedChangeOutput']
    # TODO: note, should prep exit? does unprepped data get coefs added anyways? might be able to remove if/else
    vals = classParams.keys()
    # // Run classification
    # note: stopping here, need to pythonify utils classification classifysegments and find py equlievent of apply()
    output['Layers']['classificationRaw'] = utils.Classification.classifySegments.apply(null, vals)

    return vals


if __name__ == "__main__":
    # aoi = ee.FeatureCollection(
    #     'projects/python-coded/assets/tests/test_geometry')
    # p = {'studyArea': aoi, 'start': '2018-01-01', 'end': '2020-12-31', 'prepTraining': True,
    #      'training': ee.FeatureCollection("projects/python-coded/assets/tests/test_training")}
    from coded_python.data.testing.testing_dicts import prepped, not_prepped

    # t = coded(not_prepped)
    t = coded(prepped)
    print(t)
    # collection = t
    # description = 'python-js-ccdc'
    # bucket = 'gee-upload'
    # assetid = 'projects/python-coded/assets/tests/prepped/python_prepped_samples'
    # exporting.export_table_asset(collection,description,assetid)
    # print(t.getInfo())
    # print(t.size().getInfo())
    # print(t.first().propertyNames().getInfo())
    # print(t.limit(2).getInfo())

    #
    # print(t.bandNames().getInfo())

    # exporting.export_img(t, aoi, 'ccdc_python_coefsForTraining_wth',
    #  'projects/python-coded/assets/tests/', 30, None, False, True)
