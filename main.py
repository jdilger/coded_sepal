from ee import collection
from coded_python.data.testing.testing_dicts import prepped, not_prepped
from coded_python.api import coded, coded_v2
from coded_python.utils import exporting
from coded_python.image_collections import simple_cols as cs
from rich import print
# test with filtering out null samples
prepped['training'] = prepped['training'].filterMetadata('GV_COS','not_equals',None)
print(prepped)
# t = coded(not_prepped)
change = {
    'collection' : cs.getLandsat(region=prepped['studyArea'],
    start=prepped['start'],
    end=prepped['end'])
}
general = {
    'studyArea' : prepped['studyArea']
}
classp = {
    'trainingData' : prepped['training']
}
t = coded(prepped)
t2 = coded_v2(general,change,classp)
# print(t)
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
print(t)
print(t2)
# # current version w dicts
# img = t['Layers']['Stratification']
# exporting.export_img(
#     image=img,
#     geometry=prepped['studyArea'],
#     name='python_stratification_python_dicts',
#     export_path= 'projects/python-coded/assets/tests/',
#     export_scale= 30,
#     crs= None,
#     dry_run= False,
#     test= True)