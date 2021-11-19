# def a(start:str,end:str,prepTraining:bool,studyarea:ee.FeatureCollection,training:ee.FeatureCollection,forestValue:int,classBands:list(str),breakpointBands:list(str),startYear:int,endYear:int):
#     '''coded dummy func for auto doc tring :)

#     Args:
#         start (str): start date to filter image collection by e.g. "2018-01-01"
#         end (str): end date to filter image collection by e.g. "2020-12-31"
#         prepTraining (bool): boolean argument to generate, sample, and export coefficents for training data (make CODED run faster) 
#         studyarea (ee.FeatureCollection): The study area.
#         training (ee.FeatureCollection): Training points that include a forest value and 'year' property for sampling coefficents
#         forestValue (int): The value of forest in the input mask 
#         classBands (list): class band def: default ['NDFI', 'GV', 'Shade', 'NPV', 'Soil']
#         breakpointBands (list): ????
#         startYear (int): CODED start year
#         endYear (int): CODED end year
#     '''
#     pass
from dataclasses import dataclass, field, asdict
from types import new_class
from typing import List, Union, Optional
from ee.featurecollection import FeatureCollection
from rich import print
import ee
ee.Initialize()
@dataclass
class generalParams:
    studyArea : Union[ee.FeatureCollection, ee.Geometry]
    mask: int
    startYear: int 
    endYear : int
    segs : List[str] =  field(default_factory= lambda: ['S1', 'S2', 'S3', 'S4', 'S5'])
    classBands : List[str] =  field(default_factory= lambda: ['GV', 'Shade', 'NPV', 'Soil', 'NDFI'])
    forestValue : int = 1

@dataclass
class classParams:
    imageToClassify: ee.Image 
    bandNames:  generalParams
    trainingData: Union[ee.FeatureCollection, generalParams]
    studyArea: Union[generalParams, ee.FeatureCollection, ee.Geometry]
    numberOfSegments: Union[generalParams,List[str]]

    classProperty: str = 'landcover'#TODO: this is the prop used for training classifier, should be parameter
    coefs: List[str] = field(default_factory = lambda:['INTP', 'SIN', 'COS', 'RMSE'])
    classifier: ee.Classifier = ee.Classifier.smileRandomForest(150)

    trainProp: Optional[Union[float, None]] = None
    seed: Optional[Union[int, None]] = None
    subsetTraining: Optional[bool]=False
    ancillary: Optional[Union[list,None]] = None
    ancillaryFeatures: Optional[Union[ee.Image,None]] = None

    def dict(self):
        return asdict(self)


@dataclass
class changeDetectionParams:
        collection: ee.ImageCollection
        _lambda: float = 20/10000
        minNumOfYearsScaler: float = 1.33
        dateFormat: int = 1
        minObservations: int = 3
        chiSquareProbability: float = .9
        # 'breakpointBands': params.get('breakpointBands', ['NDFI']), #TODO: ask eric about why this is here?

@dataclass
class layers:
    rawChangeOutput: ee.Image = None
    formattedChangeOutput: ee.Image = None
    mask : None = None

@dataclass
class output:
    Change_Parameters: changeDetectionParams
    General_Parameters: generalParams
    Layers: layers


dict_input = {
    'studyArea' : ee.FeatureCollection('user/TEST/fake'),
    'mask': int,
    'startYear': 2002, 
    'endYear' : 2001,
}
new_params = generalParams(**dict_input,forestValue=2)
# print(new_params)
new_params.forestValue = 5
# print(type(new_params.mask))
new_class_params = classParams(bandNames=new_params.classBands,
            numberOfSegments=new_params.segs,
            imageToClassify=ee.Image(0),
            trainingData=ee.FeatureCollection([]),
            studyArea=ee.Geometry.Point([0,0]))

new_change_params = changeDetectionParams(collection=ee.ImageCollection([]))
new_layers_params = layers()

# test output will update as other classes change
new_output = output(changeDetectionParams, generalParams, layers)
print(new_output)

# change layers
new_layers_params.mask = 9999
print(new_layers_params.mask)
print(new_output.Layers.mask)
# new output doesnt update, keep as dict
