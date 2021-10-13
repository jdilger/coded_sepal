# simple_cols.py
import ee
ee.Initialize()


def calcNDFI(image):

    # /* Do spectral unmixing */
    gv = [.0500, .0900, .0400, .6100, .3000, .1000]
    shade = [0, 0, 0, 0, 0, 0]
    npv = [.1400, .1700, .2200, .3000, .5500, .3000]
    soil = [.2000, .3000, .3400, .5800, .6000, .5800]
    cloud = [.9000, .9600, .8000, .7800, .7200, .6500]
    cf = .1  # // Not parameterized
    cfThreshold = ee.Image.constant(cf)
    unmixImage = ee.Image(image).unmix([gv, shade, npv, soil, cloud], True, True) \
        .rename(['band_0', 'band_1', 'band_2', 'band_3', 'band_4'])
    newImage = ee.Image(image).addBands(unmixImage)
    mask = newImage.select('band_4').lt(cfThreshold)
    ndfi = ee.Image(unmixImage).expression(
        '((GV / (1 - SHADE)) - (NPV + SOIL)) / ((GV / (1 - SHADE)) + NPV + SOIL)', {
            'GV': ee.Image(unmixImage).select('band_0'),
            'SHADE': ee.Image(unmixImage).select('band_1'),
            'NPV': ee.Image(unmixImage).select('band_2'),
            'SOIL': ee.Image(unmixImage).select('band_3')
        })
    out = ee.Image(newImage) \
        .addBands(ee.Image(ndfi).rename(['NDFI'])) \
        .select(['band_0', 'band_1', 'band_2', 'band_3', 'NDFI']) \
        .rename(['GV', 'Shade', 'NPV', 'Soil', 'NDFI']) \
        .updateMask(mask)
    return out


def doIndices(collection):
    def indices_image(image):
        # // NDFI function requires surface reflectance bands only
        BANDS = ['BLUE', 'GREEN', 'RED', 'NIR', 'SWIR1', 'SWIR2']
        NDFI = calcNDFI(image.select(BANDS))
        return image.addBands([NDFI])

    return collection.map(lambda i: indices_image(i))


def prepareL4L5(image):
    bandList = ['B1', 'B2', 'B3', 'B4', 'B5', 'B7', 'B6']
    nameList = ['BLUE', 'GREEN', 'RED', 'NIR', 'SWIR1', 'SWIR2', 'TEMP']
    scaling = [10000, 10000, 10000, 10000, 10000, 10000, 1000]
    scaled = ee.Image(image).select(bandList).rename(
        nameList).divide(ee.Image.constant(scaling))

    validQA = [66, 130, 68, 132]
    mask1 = ee.Image(image).select(['pixel_qa']).remap(
        validQA, ee.List.repeat(1, len(validQA)), 0)
    # // Gat valid data mask, for pixels without band saturation
    mask2 = image.select('radsat_qa').eq(0)
    mask3 = image.select(bandList).reduce(ee.Reducer.min()).gt(0)
    mask4 = image.select(bandList).reduce(ee.Reducer.max()).lt(10000)
    # // Mask hazy pixels.
    mask5 = (image.select("sr_atmos_opacity").unmask(-1)).lt(300)
    return ee.Image(image).addBands(scaled).updateMask(mask1.And(mask2).And(mask3).And(mask4).And(mask5))


def prepareL7(image):
    bandList = ['B1', 'B2', 'B3', 'B4', 'B5', 'B7', 'B6']
    nameList = ['BLUE', 'GREEN', 'RED', 'NIR', 'SWIR1', 'SWIR2', 'TEMP']
    scaling = [10000, 10000, 10000, 10000, 10000, 10000, 1000]
    scaled = ee.Image(image).select(bandList).rename(
        nameList).divide(ee.Image.constant(scaling))

    validQA = [66, 130, 68, 132]
    mask1 = ee.Image(image).select(['pixel_qa']).remap(
        validQA, ee.List.repeat(1, len(validQA)), 0)
    # // Gat valid data mask, for pixels without band saturation
    mask2 = image.select('radsat_qa').eq(0)
    mask3 = image.select(bandList).reduce(ee.Reducer.min()).gt(0)
    mask4 = image.select(bandList).reduce(ee.Reducer.max()).lt(10000)
    # // Mask hazy pixels.
    mask5 = (image.select("sr_atmos_opacity").unmask(-1)).lt(300)
    # // Slightly erode bands to get rid of artifacts due to scan lines
    temp = ee.Image(image).updateMask(
        mask1.And(mask2).And(mask3).And(mask4).And(mask5))
    mask6 = ee.Image(temp).mask().reduce(ee.Reducer.min()).focal_min(2.5)
    return ee.Image(temp).addBands(scaled).updateMask(mask6)


def prepareL8(image):

    bandList = ['B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B10']
    nameList = ['BLUE', 'GREEN', 'RED', 'NIR', 'SWIR1', 'SWIR2', 'TEMP']
    scaling = [10000, 10000, 10000, 10000, 10000, 10000, 1000]

    validTOA = [66, 68, 72, 80, 96, 100, 130, 132, 136, 144, 160, 164]
    validQA = [322, 386, 324, 388, 836, 900]

    scaled = ee.Image(image).select(bandList).rename(
        nameList).divide(ee.Image.constant(scaling))
    mask1 = ee.Image(image).select(['pixel_qa']).remap(
        validQA, ee.List.repeat(1, len(validQA)), 0)
    mask2 = image.select('radsat_qa').eq(0)
    mask3 = image.select(bandList).reduce(ee.Reducer.min()).gt(0)
    mask4 = ee.Image(image).select(['sr_aerosol']).remap(
        validTOA, ee.List.repeat(1, len(validTOA)), 0)
    return ee.Image(image).addBands(scaled).updateMask(mask1.And(mask2).And(mask3).And(mask4))


def getLandsat(**kwargs):
    start = kwargs.get('start', '1980-01-01')
    end = kwargs.get('end', '2021-01-01')
    startDoy = kwargs.get('startDOY', 1)
    endDoy = kwargs.get('endDOY', 366)
    region = kwargs.get('region', None)
    targetBands = kwargs.get('targetBands', ['BLUE', 'GREEN', 'RED', 'NIR', 'SWIR1', 'SWIR2', 'TEMP',
                                             'NDFI', 'GV', 'NPV', 'Shade', 'Soil', ])
    useMask = kwargs.get('useMask', True)
    sensors = kwargs.get(
        'sensors', {'l4': True, 'l5': True, 'l7': True, 'l8': True})

    # // Filter using new filtering  lambda
    collection4 = ee.ImageCollection('LANDSAT/LT04/C01/T1_SR') \
        .filterDate(start, end)
    collection5 = ee.ImageCollection('LANDSAT/LT05/C01/T1_SR') \
        .filterDate(start, end)
    collection7 = ee.ImageCollection('LANDSAT/LE07/C01/T1_SR') \
        .filterDate(start, end)
    collection8 = ee.ImageCollection('LANDSAT/LC08/C01/T1_SR') \
        .filterDate(start, end)

    if str(useMask).lower() == 'no':
        useMask = False

    if useMask:
        collection8 = collection8.map(prepareL8)
        collection7 = collection7.map(prepareL7)
        collection5 = collection5.map(prepareL4L5)
        collection4 = collection4.map(prepareL4L5)
    else:

        bandListL8 = ['B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B10']
        nameListL8 = ['BLUE', 'GREEN', 'RED', 'NIR', 'SWIR1', 'SWIR2', 'TEMP']

        bandListL457 = ['B1', 'B2', 'B3', 'B4', 'B5', 'B7', 'B6']
        nameListL457 = ['BLUE', 'GREEN', 'RED',
                        'NIR', 'SWIR1', 'SWIR2', 'TEMP']
        collection8 = collection8.map(
            lambda i: i.select(bandListL8).rename(nameListL8))
        collection4 = collection4.map(
            lambda i: i.select(bandListL457).rename(nameListL457))
        collection5 = collection5.map(lambda i: i.select(
            bandListL457).rename(nameListL457))
        collection7 = collection7.map(lambda i: i.select(
            bandListL457).rename(nameListL457))

    col = collection4.merge(collection5) \
        .merge(collection7) \
        .merge(collection8)
    if region:
        col = col.filterBounds(region)

    indices = doIndices(col).select(targetBands)

    if sensors['l5'] is not True:
        indices = indices.filterMetadata(
            'SATELLITE', 'not_equals', 'LANDSAT_5')

    if sensors['l4'] is not True:
        indices = indices.filterMetadata(
            'SATELLITE', 'not_equals', 'LANDSAT_4')

    if sensors['l7'] is not True:
        indices = indices.filterMetadata(
            'SATELLITE', 'not_equals', 'LANDSAT_7')

    if sensors['l8'] is not True:
        indices = indices.filterMetadata(
            'SATELLITE', 'not_equals', 'LANDSAT_8')

    indices = indices.filter(ee.Filter.dayOfYear(startDoy, endDoy))

    return ee.ImageCollection(indices)


if __name__ == "__main__":
    aoi = ee.FeatureCollection(
        'projects/python-coded/assets/tests/test_geometry')
    p = {'region': aoi}
    col = getLandsat(**p)
    print(col.size().getInfo())
    print(col.first().bandNames().getInfo())
