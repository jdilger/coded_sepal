from rich import print
import ee
ee.Initialize()

class python_coded:
    raw = ee.FeatureCollection("projects/python-coded/assets/tests/test_training")
    prepped_samples = ee.FeatureCollection("projects/python-coded/assets/tests/prepped/py_sample_with_pred")

class js_coded:
    raw = ee.FeatureCollection("projects/python-coded/assets/tests/test_training")
    prepped_samples = ee.FeatureCollection("projects/python-coded/assets/tests/prepped/js_sample_with_pred")

if __name__ == '__main__':
    js = js_coded()
    py = python_coded()

    js_first_nn = js.prepped_samples.filterMetadata('GV_COS','not_equals',None).first().toDictionary().getInfo()
    py_first_nn = py.prepped_samples.filterMetadata('GV_COS','not_equals',None).first().toDictionary().getInfo()

    print(js_first_nn == py_first_nn)
