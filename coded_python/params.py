import os
container_folder = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..'
))
from dataclasses import dataclass, field, asdict
from typing import List, Union, Optional
from coded_python.ccdc import ccdc
import ee
# dev
from rich import print

ee.Initialize()

@dataclass
class changeDetectionParams:
    collection: ee.ImageCollection
    _lambda: float = 20/10000
    minNumOfYearsScaler: float = 1.33
    dateFormat: int = 1
    minObservations: int = 3
    chiSquareProbability: float = .9

    def dict(self):
        return asdict(self)
    
    def dict_ee(self):
        tmp = asdict(self)
        tmp['lambda'] = tmp.pop('_lambda')
        return tmp
        
    def get_start_end_from_col(self, start_or_end:str, col:ee.ImageCollection=None)->ee.Number:
        if col is None:
            col = self.collection
        
        if start_or_end.lower() == 'start':
            year = col.aggregate_min(
            'year')
        elif start_or_end.lower() == 'end':
            year = col.aggregate_max(
                'year')
        return ee.Number(year)

@dataclass
class generalParams:
    studyArea : Union[ee.FeatureCollection, ee.Geometry]
    # todo: mask should not be none
    mask: Union[int,None] = None
    startYear: Union[int, None] = None
    endYear : Union[int,None] = None
    segs : List[str] =  field(default_factory= lambda: ['S1', 'S2', 'S3', 'S4', 'S5'])
    classBands : List[str] =  field(default_factory= lambda: ['GV', 'Shade', 'NPV', 'Soil', 'NDFI'])
    coefs : List[str] =  field(default_factory= lambda: ['INTP', 'SIN', 'COS', 'RMSE', 'SLP'])
    forestValue : int = 1
    
    def dict(self):
        return asdict(self)

@dataclass
class classParams:
    imageToClassify: ee.Image 
    bandNames:  Union[List[str],generalParams]
    trainingData: Union[ee.FeatureCollection, generalParams]
    studyArea: Union[generalParams, ee.FeatureCollection, ee.Geometry]
    numberOfSegments: int

    classProperty: str = 'landcover'#TODO: this is the prop used for training classifier, should be parameter
    coefs: List[str] = field(default_factory = lambda:['INTP', 'SIN', 'COS', 'RMSE'])
    classifier: ee.Classifier = ee.Classifier.smileRandomForest(150)

    trainProp: Optional[Union[float, None]] = None
    seed: Optional[Union[int, None]] = None
    subsetTraining: Optional[bool]=False
    ancillary: Optional[Union[list,None]] = None
    ancillaryFeatures: Optional[Union[ee.Image,None]] = None
    prepTraining: Optional[bool] = False

    def dict(self):
        return asdict(self)

    def prep_samples(self, general : generalParams, samples:ee.FeatureCollection = None)-> ee.FeatureCollection:
        """ prepares sample collection by adding ccdc coefs from the formatted change output"""

        if samples is None:
            samples = self.trainingData
        
        def prep_sample(feat: ee.Feature) -> ee.Feature:
            coefsForTraining = ccdc.getMultiCoefs(
                self.imageToClassify,
                ee.Image.constant(feat.getNumber('year')),
                general.classBands,
                general.coefs,
                True,
                general.segs,
                'before')

            sampleForTraining = feat.setMulti(coefsForTraining.reduceRegion(**{
                'geometry': feat.geometry(),
                'scale': 90,
                'reducer': ee.Reducer.mean()
            }))

            return sampleForTraining
        
        return ee.FeatureCollection(samples.map(prep_sample))

@dataclass
class OutputLayers:
    rawChangeOutput: ee.Image
    formattedChangeOutput: ee.Image
    mask : ee.Image
    classificationRaw :ee.Image
    classification : ee.Image
    magnitude : ee.Image



@dataclass
class Output:
    Change_Parameters: changeDetectionParams
    General_Parameters: generalParams
    Layers: OutputLayers

@dataclass
class PostProcess:
    Stratification:ee.Image
    Degradation: ee.Image
    Deforestation: ee.Image
    Both : ee.Image
    classificationStudyPeriod :ee.Image
    dateOfDeforestation : ee.Image
    dateOfDegradation : ee.Image