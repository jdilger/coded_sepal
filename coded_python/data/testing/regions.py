# regions.py
import ee
from ee.featurecollection import FeatureCollection
ee.Initialize()
class test_study_area:
    region : ee.FeatureCollection = ee.FeatureCollection('projects/python-coded/assets/tests/regions/test_geometry')