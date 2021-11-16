from collections import namedtuple
import sys
import os

container_folder = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..'
))
sys.path.insert(0, container_folder)

import ee
from coded_python.ccdc import ccdc
from coded_python.ccdc import classification as rf
from coded_python.image_collections import simple_cols as cs
from coded_python.params import classParams, changeDetectionParams, generalParams, Output, OutputLayers, PostProcess

ee.Initialize()

def prep_collection_v2(change: changeDetectionParams, general: generalParams):
    change.collection = change.collection \
        .filterBounds(general.studyArea).select(general.classBands) \
        .map(lambda i: i.set('year', i.date().get('year')))

def run_classification_v2(general: generalParams,
        classp :classParams):
    #TODO : anywhere NDFI is string maybe replace w breakpoint_bands?
    classificationRaw = rf.classifySegments(
        numberOfSegments=classp.numberOfSegments,
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
    mask = general.mask
    if mask is None:
        mask = classificationRaw.select(0).eq(general.forestValue)

    tMags = classp.imageToClassify.select('.*NDFI_MAG').lt(0) \
        .select(ee.List.sequence(0, len(general.segs) - 2)) 
    
    factor = ee.Image(1).addBands(tMags)
    classificationRaw = classificationRaw.multiply(factor).selfMask()

    classification = classificationRaw \
        .select(ee.List.sequence(1, len(general.segs) - 1)) \
        .int8() \
        .updateMask(mask)

    magnitude = classp.imageToClassify.select('.*NDFI_MAG')

    Out = namedtuple('Out',"classificationRaw mask classification magnitude")
    return Out(classificationRaw, mask, classification, magnitude)

def coded_v2(input_gen_params: dict, input_change_params:dict, input_class_params:dict):
    change_params = changeDetectionParams(**input_change_params)
    general_params = generalParams(**input_gen_params)
    
    # check if start and end year are input
    if general_params.startYear is None:
        general_params.startYear = change_params.get_start_end_from_col('start')
    if general_params.endYear is None:
        general_params.endYear = change_params.get_start_end_from_col('end')
    
    prep_collection_v2(change_params, general_params)

    raw_change = ee.Algorithms.TemporalSegmentation.Ccdc(
        **{'collection': change_params.collection,
        'minNumOfYearsScaler' : change_params.minNumOfYearsScaler, 
        'dateFormat' : change_params.dateFormat,
        'minObservations' : change_params.minObservations,
        'chiSquareProbability' : change_params.chiSquareProbability,
        'lambda' : change_params._lambda}
        )

    formated_change = ccdc.buildCcdImage(
        raw_change,
        len(general_params.segs),
        general_params.classBands,
        )

    # make classification params
    class_params = classParams(
        **input_class_params,
        imageToClassify=formated_change,
        bandNames=general_params.classBands,
        studyArea=general_params.studyArea,
        numberOfSegments=len(general_params.segs)
        )
    
    if class_params.prepTraining:
        class_params.trainingData = class_params.prep_samples(general_params)

    out_classification = run_classification_v2(general_params,class_params)

    output_layers = OutputLayers(
        rawChangeOutput= raw_change,
        formattedChangeOutput = class_params.imageToClassify,
        mask = out_classification.mask,
        classificationRaw = out_classification.classificationRaw,
        classification = out_classification.classification,
        magnitude = out_classification.magnitude,
        )
    # rename dataclasses with CamelCase
    return Output(Change_Parameters=change_params,
        General_Parameters=general_params,
        Layers=output_layers)


# postprocessing
def degradation_and_deforestation(classificationStudyPeriod:ee.Image, forestValue:int):
    deg = classificationStudyPeriod.eq(forestValue) \
        .reduce(ee.Reducer.max()).rename('Degradation')
    defor = classificationStudyPeriod.neq(forestValue) \
        .reduce(ee.Reducer.max()).rename('Deforestation')
    both = deg.And(defor)
    return deg, defor, both

def tbreaks(output : Output):
    tBreaks = output.Layers.formattedChangeOutput \
        .select('.*tBreak') \
        .select(ee.List.sequence(0,
             len(output.General_Parameters.segs) - 2)
             )
    tBreaksInterval = tBreaks.floor().gte(ee.Number(output.General_Parameters.startYear)) \
        .And(tBreaks.floor().lte(ee.Number(output.General_Parameters.endYear)))

    return tBreaks, tBreaksInterval

def make_degradation_and_deforestation(output: Output):
    tBreaks, tBreaksInterval = tbreaks(output)
    classificationStudyPeriod =  output.Layers.classification.updateMask(tBreaksInterval)
    deg, defor, both = degradation_and_deforestation(
        classificationStudyPeriod,
        output.General_Parameters.forestValue)

    Degradation = deg.And(both.Not()).selfMask().int8()
    Deforestation = defor.And(both.Not()).selfMask().int8()
    Both = both.selfMask().int8()
    # note from   classificationStudyPeriod to both all return errors if some data are missing values...
    # some how when we get to the end it works though, so is this needed?
    dateOfDegradation = classificationStudyPeriod \
        .eq(output.General_Parameters.forestValue) \
        .multiply(tBreaks) \
        .multiply(tBreaksInterval)
    
    dateOfDeforestation = classificationStudyPeriod \
        .neq(output.General_Parameters.forestValue) \
        .multiply(tBreaks) \
        .multiply(tBreaksInterval)

    Degradation_Deforestation = namedtuple("Degradation_Deforestation",
         "Deforestation Degradation Both dateOfDeforestation dateOfDegradation classificationStudyPeriod")
    return Degradation_Deforestation(Deforestation,Degradation, Both, dateOfDeforestation, dateOfDegradation, classificationStudyPeriod)

def make_stratification(mask:ee.Image,degradation:ee.Image, deforestation:ee.Image, both:ee.Image):
    # // Make single layer stratification
    stratification = mask.remap([0,1],[2,1]) \
        .where(degradation, 3) \
        .where(deforestation, 4) \
        .where(both, 5)

    return stratification.rename('stratification').int8()

def post_process(outputs :Output):
    DegDefor = make_degradation_and_deforestation(outputs)

    stratification = make_stratification(mask=outputs.General_Parameters.mask,
        degradation=DegDefor.Degradation,
        deforestation= DegDefor.Deforestation,
        both=DegDefor.Both)
    
    return PostProcess(Stratification=stratification,
        Degradation=DegDefor.Degradation,
        Deforestation= DegDefor.Deforestation ,
        Both= DegDefor.Both,
        dateOfDeforestation = DegDefor.dateOfDeforestation,
        dateOfDegradation = DegDefor.dateOfDegradation,
        classificationStudyPeriod = DegDefor.classificationStudyPeriod
        )   

