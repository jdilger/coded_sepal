# testapi.py
import unittest
import ee
import sys
import os

container_folder = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..'
))
sys.path.insert(0, container_folder)
from coded_python.api import *
from coded_python.ccdc import *

# ////////////////////////////////

ee.Initialize()


class ParameterTestCase(unittest.TestCase):
    def testUnittest(self):
        assert 'A' == 'A'

    def testParameters(self):
        default_endmembers = {
            'gv': [.0500, .0900, .0400, .6100, .3000, .1000],
            'shade': [0, 0, 0, 0, 0, 0],
            'npv': [.1400, .1700, .2200, .3000, .5500, .3000],
            'soil': [.2000, .3000, .3400, .5800, .6000, .5800],
            'cloud': [.9000, .9600, .8000, .7800, .7200, .6500],
        }
        default_cloudThreshold = .1
        self.assertEqual(PARAMTERS.endmembers, default_endmembers)
        self.assertEqual(PARAMTERS.cloudThreshold, default_cloudThreshold)


class PrepCollection(unittest.TestCase):
    def testPrepCollection(self):
        col = ee.ImageCollection("LANDSAT/LC08/C01/T2_SR") \
            .filterDate('2018-01-01', '2020-12-31')
        aoi = ee.FeatureCollection(
            'projects/python-coded/assets/tests/test_geometry')
        cdp = {'collection': col}
        gp = {'studyArea': aoi,
              'classBands': ['B1', 'B2', 'B3']}

        pre_size = cdp['collection'].size().getInfo()
        pre_bands = cdp['collection'].first().bandNames().getInfo()

        prep_collection(cdp, gp)

        post_size = cdp['collection'].size().getInfo()
        post_img = cdp['collection'].first()

        post_bands = post_img.bandNames().getInfo()

        self.assertLess(post_size, pre_size)
        self.assertIsInstance(post_img, ee.Image)
        self.assertIn('year', post_img.propertyNames().getInfo())
        self.assertListEqual(gp['classBands'], post_bands)
        self.assertNotEqual(pre_bands, post_bands)


if __name__ == '__main__':
    unittest.main()
