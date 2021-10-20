# regions.py
import ee
ee.Initialize()
class test_study_area:
    region : ee.FeatureCollection = ee.FeatureCollection('projects/python-coded/assets/tests/regions/test_geometry')