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
from coded_python.params import classParams, changeDetectionParams, generalParams, Output, OutputLayers

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

    if general.mask is None:
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