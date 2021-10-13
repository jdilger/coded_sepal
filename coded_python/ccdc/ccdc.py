# ccdc.py
# ccdc.js - utils.CCDC.buildCcdImage(
#     buildMagnitude
#         buildSegmentTag
#     buildRMSE
#         buildSegmentTag
#     buildCoefs
#         buildSegmentTag
#         buildBandTag
#     buildStartEndBreakProb
#         buildSegmentTag
import ee
ee.Initialize()

# /**
#  * Normalize the intercept to the middle of the segment time period, instead
#  * of the 0 time period.
#  * @param {ee.Image} intercept Image band representing model intercept
#  * @param {ee.Image} start Image band representing model slope date
#  * @param {ee.Image} end Image band representing model end date
#  * @param {ee.Image} slope Image band representing model slope
#  * @returns {ee.Image} Image band representing normalized intercept.
#  */


def normalizeIntercept(intercept, start, end, slope):
    middleDate = ee.Image(start).add(ee.Image(end)).divide(2)
    slopeCoef = ee.Image(slope).multiply(middleDate)
    return ee.Image(intercept).add(slopeCoef)

# /**
#  * Filter coefficients for a given date using a mask
#  * @param {ee.Image} ccdResults CCD results in long multi-band format
#  * @param {string} date Date in the same format that CCD was run with
#  * @param {string} band Band to select.
#  * @param {string} coef Coef to select. Options are "INTP", "SLP", "COS", "SIN", "COS2",
#                                   "SIN2", "COS3", "SIN3", "RMSE", "MAG"
#  * @paramg {ee.List} segNames List of segment names to use.
#  * @param {String} behavior Method to find intersecting ('normal') or closest
#  *                                segment to given date ('before' or 'after') if no segment
#  *                                intersects directly
#  * @returns {ee.Image} Single band image with the values for the selected band/coefficient
#  */


def filterCoefs(ccdResults, date, band, coef, segNames, behavior):

    startBands = ccdResults.select(".*_tStart").rename(segNames)
    endBands = ccdResults.select(".*_tEnd").rename(segNames)

    # // Get all segments for a given band/coef. Underscore in concat ensures
    # // that bands with similar names are not selected twice (e.g. GREEN, GREENNESS)
    selStr = ".*".join(['', band, coef])  # // Client side concat
    coef_bands = ccdResults.select(selStr)

    # // Select a segment based on conditions
    if behavior == "normal":
        start = startBands.lte(date)
        end = endBands.gte(date)
        segmentMatch = start.And(end)
        outCoef = coef_bands.updateMask(
            segmentMatch).reduce(ee.Reducer.firstNonNull())

    elif behavior == "after":
        segmentMatch = endBands.gt(date)
        outCoef = coef_bands.updateMask(
            segmentMatch).reduce(ee.Reducer.firstNonNull())

    elif behavior == "before":
        # // Mask start to avoid comparing against zero, mask after to remove zeros from logical comparison
        segmentMatch = startBands.selfMask().lt(date).selfMask()
        outCoef = coef_bands.updateMask(
            segmentMatch).reduce(ee.Reducer.lastNonNull())

    return outCoef

# /**
#  * Get image of with a single coefficient for all bands
#  * @param {ee.Image} ccd results CCD results in long multi-band format
#  * @param {string} date Date in the same format that CCD was run with
#  * @param {array} bandList List of all bands to include.
#  * @param {array} coef Coef to select. Options are "INTP", "SLP", "COS", "SIN", "COS2",
#  *                                    "SIN2", "COS3", "SIN3", "RMSE", "MAG"
#  * @paramg {ee.List} segNames List of segment names to use.
#  * @param {string} behavior Method to find intersecting ('normal') or closest
#  *                                    segment to given date ('before' or 'after') if no segment
#  *                                    intersects directly
#  * @returns {ee.Image} coefs Image with the values for the selected bands x coefficient
#  */


def getCoef(ccdResults, date, bandList, coef, segNames, behavior):
    def inner(band):
        band_coef = filterCoefs(ccdResults, date, band,
                                coef, segNames, behavior)
        return band_coef.rename(f"{band}_{coef}")  # // Client side concat

    coefs = ee.Image(list(map(inner, bandList)))  # // Client side map
    return coefs

# /**
#  * Apply normalization to intercepts
#  * @param {ee.Image} bandCoefs Band x coefficients image. Must include slopes
#  * @param {ee.Image} segStart Image with dates representing the start of the segment
#  * @param {ee.Image} segEnd Image with dates representing the end of the segment
#  * @returns {ee.Image} bandCoefs Updated input image with normalized intercepts
#  */


def applyNorm(bandCoefs, segStart, segEnd):
    intercepts = bandCoefs.select(".*INTP")
    slopes = bandCoefs.select(".*SLP")
    normalized = normalizeIntercept(intercepts, segStart, segEnd, slopes)
    return bandCoefs.addBands(**{'srcImg': normalized, 'overwrite': True})


def buildSegmentTag(nSegments: int) -> ee.List:
    # note original code can't cast int to string w python
    # ee.List.sequence(1, nSegments).map(lambda i: ee.String('S').cat(ee.Number(i).int()))
    seq = list(map(lambda i: f"S{str(i+1)}", range(nSegments)))
    return ee.List(seq)
# /**
# * Create sequence of band names for a given string tag
# * @param {string} tag String tag to use (e.g. 'RMSE')
# * @param {array} bandList List of band names to combine with tag
# * @returns {ee.List) List of band names combined with tag name
# */

# might be deprecated


def buildBandTag(tag, bandList):
    bands = ee.List(bandList)
    return bands.map(lambda s: ee.String(s).cat('_' + tag))


# /**
# * Extract CCDC magnitude image from current CCDC result format
# * @param {ee.Image} fit Image with CCD results
# * @param {number} nSegments Number of segments to extract
# * @param {array} bandList  Client-side list with band names to use
# * @returns {ee.Image) Image with magnitude of change per segment per band
# */


def buildMagnitude(fit, nSegments, bandList):
    segmentTag = buildSegmentTag(nSegments)
    zeros = ee.Image(ee.Array(ee.List.repeat(0, nSegments)))
    # // Pad zeroes for pixels that have less than nSegments and then slice the first nSegment values

    def retrieveMags(band):
        magImg = fit.select(band + '_magnitude').arrayCat(zeros,
                                                          0).float().arraySlice(0, 0, nSegments)
        tags = segmentTag.map(lambda x: ee.String(
            x).cat('_').cat(band).cat('_MAG'))
        return magImg.arrayFlatten([tags])

    return ee.Image(list(map(retrieveMags, bandList)))

# /**
# * Extract CCDC RMSE image from current CCDC formatted results
# * @param {ee.Image} fit Image with CCDC results
# * @param {number}  nSegments Number of segments to extract
# * @param {array} bandList  Client-side list with band names to use
# * @returns {ee.Image) Image with RMSE of each segment per band
# */


def buildRMSE(fit, nSegments, bandList):
    segmentTag = buildSegmentTag(nSegments)
    zeros = ee.Image(ee.Array(ee.List.repeat(0, nSegments)))
    # // Pad zeroes for pixels that have less than 6 segments and then slice the first 6 values

    def retrieveMags(band):
        magImg = fit.select(band + '_rmse').arrayCat(zeros,
                                                     0).float().arraySlice(0, 0, nSegments)
        tags = segmentTag.map(lambda x: ee.String(
            x).cat('_').cat(band).cat('_RMSE'))
        return magImg.arrayFlatten([tags])

    return ee.Image(list(map(retrieveMags, bandList)))

# /**
# * Extract CCDC Coefficients from current CCDC formatted result
# * @param {ee.Image} fit Image with CCD results
# * @param {number} nSegments Number of segments to extract
# * @param {array} bandList  Client-side list with band names to use
# * @returns {ee.Image) Image with coefficients per band
# */


def buildCoefs(fit, nSegments, bandList):
    # nBands = len(bandList)
    segmentTag = buildSegmentTag(nSegments)
    # bandTag = buildBandTag('coef', bandList)
    harmonicTag = ['INTP', 'SLP', 'COS', 'SIN', 'COS2', 'SIN2', 'COS3', 'SIN3']

    zeros = ee.Image(
        ee.Array([ee.List.repeat(0, len(harmonicTag))])).arrayRepeat(0, nSegments)

    def retrieveCoefs(band):
        coefImg = fit.select(band + '_coefs').arrayCat(zeros,
                                                       0).float().arraySlice(0, 0, nSegments)
        tags = segmentTag.map(lambda x: ee.String(
            x).cat('_').cat(band).cat('_coef'))
        return coefImg.arrayFlatten([tags, harmonicTag])

    return ee.Image(list(map(retrieveCoefs, bandList)))

# /**
# * Extract data for CCDC 1D-array, non-spectral bands (tStart, tEnd, tBreak, changeProb or numObs)
# * @param {ee.Image} fit Image with CCD results
# * @param {integer} nSegments Number of segments to extract
# * @param {string} tag Client-side string to use as name in the output bands
# * @returns {ee.Image) Image with values for tStart, tEnd, tBreak, changeProb or numObs
# */


def buildStartEndBreakProb(fit, nSegments, tag):
    segmentTag = buildSegmentTag(nSegments).map(
        lambda s: ee.String(s).cat('_'+tag))

    zeros = ee.Array(0).repeat(0, nSegments)
    magImg = fit.select(tag).arrayCat(
        zeros, 0).float().arraySlice(0, 0, nSegments)

    return magImg.arrayFlatten([segmentTag])

# /**
# * Transform ccd results from array image to "long" multiband format
# * @param {ee.Image} fit Image with CCD results
# * @param {number} nSegments Number of segments to extract
# * @param {array} bandList Client-side list with band names to use
# * @returns {ee.Image) Image with all results from CCD in 'long' image format
# */


def buildCcdImage(fit, nSegments, bandList):
    magnitude = buildMagnitude(fit, nSegments, bandList)
    rmse = buildRMSE(fit, nSegments, bandList)

    coef = buildCoefs(fit, nSegments, bandList)
    tStart = buildStartEndBreakProb(fit, nSegments, 'tStart')
    tEnd = buildStartEndBreakProb(fit, nSegments, 'tEnd')
    tBreak = buildStartEndBreakProb(fit, nSegments, 'tBreak')
    probs = buildStartEndBreakProb(fit, nSegments, 'changeProb')
    nobs = buildStartEndBreakProb(fit, nSegments, 'numObs')
    return ee.Image.cat(coef, rmse, magnitude, tStart, tEnd, tBreak, probs, nobs)

# /**
#  * Get image of with bands x coefficients given in a list
#  * @param {ee.Image} ccd results CCD results in long multi-band format
#  * @param {string} date Date in the same format that CCD was run with
#  * @param {array} bandList List of all bands to include. Options are "B1", "B2", "B3", "B4", "B5", "B6", "B7"
#  * @param {list} coef_list List of coefs to select. Options are "INTP", "SLP", "COS", "SIN", "COS2",
#  *                                    "SIN2", "COS3", "SIN3", "RMSE", "MAG"
#  * @param {boolean} cond Normalize intercepts? If true, requires "INTP" and "SLP" to be selected
#  *                                    in coef_list.
#  * @param {ee.List} segNames List of segment names to use.
#  * @param {string} behavior Method to find intersecting ('normal') or closest
#  *                                    segment to given date ('before' or 'after') if no segment
#  *                                    intersects directly. 'Auto' does 'after' first, then
#  *                                    fills any gaps with the results of 'before'
#  * @returns {ee.Image} coefs Image with the values for the selected bands x coefficients
#  */


def getMultiCoefs(ccdResults, date, bandList, coef_list, cond, segNames, behavior):
    # js todo   // TODO: can be rewritten to avoid redundant code, welcome :)
    def inner(coef, behavior):
        inner_coef = getCoef(ccdResults, date, bandList,
                             coef, segNames, behavior)
        return inner_coef
    if behavior == "auto":

        # // Non normalized, after
        # #js todo // TODO: create a single inner function.
        # def innerAfter(coef):
        #     inner_coef = getCoef(ccdResults, date, bandList, coef, segNames, "after")
        #     return inner_coef

        coefsAfter = ee.Image(
            list(map(lambda i: inner(i, "after"), coef_list)))

        # # // Non normalized, before
        # def innerBefore(coef):
        #     inner_coef = getCoef(ccdResults, date, bandList, coef, segNames, "before")
        #     return inner_coef

        coefsBefore = ee.Image(
            list(map(lambda i: inner(i, "before"), coef_list)))

        # // Normalized
        # // Do after
        segStartAfter = filterCoefs(
            ccdResults, date, "", "tStart", segNames, "after")
        segEndAfter = filterCoefs(
            ccdResults, date, "", "tEnd", segNames, "after")
        normCoefsAfter = applyNorm(coefsAfter, segStartAfter, segEndAfter)

        # // Do before
        segStartBefore = filterCoefs(
            ccdResults, date, "", "tStart", segNames, "before")
        segEndBefore = filterCoefs(
            ccdResults, date, "", "tEnd", segNames, "before")
        normCoefsBefore = applyNorm(coefsBefore, segStartBefore, segEndBefore)

        # // Combine into a single layer. The order below guarantees that any gaps
        # // in afterCoef are filled with beforeCoef.
        outCoefs = ee.ImageCollection(
            [normCoefsBefore, normCoefsAfter]).mosaic()

    else:

        # # // Non normalized
        # inner = function(coef){
        # inner_coef = getCoef(ccdResults, date, bandList, coef, segNames, behavior)
        # return inner_coef

        coefs = ee.Image(list(map(lambda i: inner(i, behavior), coef_list)))

        # // Normalized
        segStart = filterCoefs(ccdResults, date, "",
                               "tStart", segNames, behavior)
        segEnd = filterCoefs(ccdResults, date, "", "tEnd", segNames, behavior)
        normCoefs = applyNorm(coefs, segStart, segEnd)

        outCoefs = ee.Algorithms.If(cond, normCoefs, coefs)

    return ee.Image(outCoefs)


if __name__ == "__main__":
    import api
    aoi = ee.FeatureCollection(
        'projects/python-coded/assets/tests/test_geometry')
    p = {'studyArea': aoi}
    generalParams = api.make_general_params(p)
    # // CODED Change Detection Parameters
    changeDetectionParams = api.make_change_detection_params(
        p, studyArea=generalParams['studyArea'])
    output = api.make_output_dict(changeDetectionParams, generalParams)
    api.run_ccdc(output, changeDetectionParams)
    # print(output['Layers']['rawChangeOutput'].bandNames().getInfo())

    # tests
    a = buildSegmentTag(5)
    testBuildSegs = a.getInfo() == ['S1', 'S2', 'S3', 'S4', 'S5']
    print('testBuildSegs', testBuildSegs)

    fit = output['Layers']['rawChangeOutput']
    nSegments = len(generalParams['segs'])
    bandList = generalParams['classBands']

    magnitude = buildMagnitude(fit, nSegments, bandList)
    testMag = magnitude.bandNames().getInfo() == ['S1_GV_MAG', 'S2_GV_MAG', 'S3_GV_MAG', 'S4_GV_MAG', 'S5_GV_MAG', 'S1_Shade_MAG', 'S2_Shade_MAG', 'S3_Shade_MAG', 'S4_Shade_MAG', 'S5_Shade_MAG', 'S1_NPV_MAG',
                                                  'S2_NPV_MAG', 'S3_NPV_MAG', 'S4_NPV_MAG', 'S5_NPV_MAG', 'S1_Soil_MAG', 'S2_Soil_MAG', 'S3_Soil_MAG', 'S4_Soil_MAG', 'S5_Soil_MAG', 'S1_NDFI_MAG', 'S2_NDFI_MAG', 'S3_NDFI_MAG', 'S4_NDFI_MAG', 'S5_NDFI_MAG']
    print('testMag', testMag)
    rmse = buildRMSE(fit, nSegments, bandList)
    testRMSE = rmse.bandNames().getInfo() == ['S1_GV_RMSE', 'S2_GV_RMSE', 'S3_GV_RMSE', 'S4_GV_RMSE', 'S5_GV_RMSE', 'S1_Shade_RMSE', 'S2_Shade_RMSE', 'S3_Shade_RMSE', 'S4_Shade_RMSE', 'S5_Shade_RMSE', 'S1_NPV_RMSE', 'S2_NPV_RMSE',
                                              'S3_NPV_RMSE', 'S4_NPV_RMSE', 'S5_NPV_RMSE', 'S1_Soil_RMSE', 'S2_Soil_RMSE', 'S3_Soil_RMSE', 'S4_Soil_RMSE', 'S5_Soil_RMSE', 'S1_NDFI_RMSE', 'S2_NDFI_RMSE', 'S3_NDFI_RMSE', 'S4_NDFI_RMSE', 'S5_NDFI_RMSE']
    print('testRMSE', testRMSE)

    coef = buildCoefs(fit, nSegments, bandList)
    testcoef = coef.bandNames().getInfo() == ['S1_GV_coef_INTP', 'S1_GV_coef_SLP', 'S1_GV_coef_COS', 'S1_GV_coef_SIN', 'S1_GV_coef_COS2', 'S1_GV_coef_SIN2', 'S1_GV_coef_COS3', 'S1_GV_coef_SIN3', 'S2_GV_coef_INTP', 'S2_GV_coef_SLP', 'S2_GV_coef_COS', 'S2_GV_coef_SIN', 'S2_GV_coef_COS2', 'S2_GV_coef_SIN2', 'S2_GV_coef_COS3', 'S2_GV_coef_SIN3', 'S3_GV_coef_INTP', 'S3_GV_coef_SLP', 'S3_GV_coef_COS', 'S3_GV_coef_SIN', 'S3_GV_coef_COS2', 'S3_GV_coef_SIN2', 'S3_GV_coef_COS3', 'S3_GV_coef_SIN3', 'S4_GV_coef_INTP', 'S4_GV_coef_SLP', 'S4_GV_coef_COS', 'S4_GV_coef_SIN', 'S4_GV_coef_COS2', 'S4_GV_coef_SIN2', 'S4_GV_coef_COS3', 'S4_GV_coef_SIN3', 'S5_GV_coef_INTP', 'S5_GV_coef_SLP', 'S5_GV_coef_COS', 'S5_GV_coef_SIN', 'S5_GV_coef_COS2', 'S5_GV_coef_SIN2', 'S5_GV_coef_COS3', 'S5_GV_coef_SIN3', 'S1_Shade_coef_INTP', 'S1_Shade_coef_SLP', 'S1_Shade_coef_COS', 'S1_Shade_coef_SIN', 'S1_Shade_coef_COS2', 'S1_Shade_coef_SIN2', 'S1_Shade_coef_COS3', 'S1_Shade_coef_SIN3', 'S2_Shade_coef_INTP', 'S2_Shade_coef_SLP', 'S2_Shade_coef_COS', 'S2_Shade_coef_SIN', 'S2_Shade_coef_COS2', 'S2_Shade_coef_SIN2', 'S2_Shade_coef_COS3',
                                              'S2_Shade_coef_SIN3', 'S3_Shade_coef_INTP', 'S3_Shade_coef_SLP', 'S3_Shade_coef_COS', 'S3_Shade_coef_SIN', 'S3_Shade_coef_COS2', 'S3_Shade_coef_SIN2', 'S3_Shade_coef_COS3', 'S3_Shade_coef_SIN3', 'S4_Shade_coef_INTP', 'S4_Shade_coef_SLP', 'S4_Shade_coef_COS', 'S4_Shade_coef_SIN', 'S4_Shade_coef_COS2', 'S4_Shade_coef_SIN2', 'S4_Shade_coef_COS3', 'S4_Shade_coef_SIN3', 'S5_Shade_coef_INTP', 'S5_Shade_coef_SLP', 'S5_Shade_coef_COS', 'S5_Shade_coef_SIN', 'S5_Shade_coef_COS2', 'S5_Shade_coef_SIN2', 'S5_Shade_coef_COS3', 'S5_Shade_coef_SIN3', 'S1_NPV_coef_INTP', 'S1_NPV_coef_SLP', 'S1_NPV_coef_COS', 'S1_NPV_coef_SIN', 'S1_NPV_coef_COS2', 'S1_NPV_coef_SIN2', 'S1_NPV_coef_COS3', 'S1_NPV_coef_SIN3', 'S2_NPV_coef_INTP', 'S2_NPV_coef_SLP', 'S2_NPV_coef_COS', 'S2_NPV_coef_SIN', 'S2_NPV_coef_COS2', 'S2_NPV_coef_SIN2', 'S2_NPV_coef_COS3', 'S2_NPV_coef_SIN3', 'S3_NPV_coef_INTP', 'S3_NPV_coef_SLP', 'S3_NPV_coef_COS', 'S3_NPV_coef_SIN', 'S3_NPV_coef_COS2', 'S3_NPV_coef_SIN2', 'S3_NPV_coef_COS3', 'S3_NPV_coef_SIN3', 'S4_NPV_coef_INTP', 'S4_NPV_coef_SLP', 'S4_NPV_coef_COS',
                                              'S4_NPV_coef_SIN', 'S4_NPV_coef_COS2', 'S4_NPV_coef_SIN2', 'S4_NPV_coef_COS3', 'S4_NPV_coef_SIN3', 'S5_NPV_coef_INTP', 'S5_NPV_coef_SLP', 'S5_NPV_coef_COS', 'S5_NPV_coef_SIN', 'S5_NPV_coef_COS2', 'S5_NPV_coef_SIN2', 'S5_NPV_coef_COS3', 'S5_NPV_coef_SIN3', 'S1_Soil_coef_INTP', 'S1_Soil_coef_SLP', 'S1_Soil_coef_COS', 'S1_Soil_coef_SIN', 'S1_Soil_coef_COS2', 'S1_Soil_coef_SIN2', 'S1_Soil_coef_COS3', 'S1_Soil_coef_SIN3', 'S2_Soil_coef_INTP', 'S2_Soil_coef_SLP', 'S2_Soil_coef_COS', 'S2_Soil_coef_SIN', 'S2_Soil_coef_COS2', 'S2_Soil_coef_SIN2', 'S2_Soil_coef_COS3', 'S2_Soil_coef_SIN3', 'S3_Soil_coef_INTP', 'S3_Soil_coef_SLP', 'S3_Soil_coef_COS', 'S3_Soil_coef_SIN', 'S3_Soil_coef_COS2', 'S3_Soil_coef_SIN2', 'S3_Soil_coef_COS3', 'S3_Soil_coef_SIN3', 'S4_Soil_coef_INTP', 'S4_Soil_coef_SLP', 'S4_Soil_coef_COS', 'S4_Soil_coef_SIN', 'S4_Soil_coef_COS2', 'S4_Soil_coef_SIN2', 'S4_Soil_coef_COS3', 'S4_Soil_coef_SIN3', 'S5_Soil_coef_INTP', 'S5_Soil_coef_SLP', 'S5_Soil_coef_COS', 'S5_Soil_coef_SIN', 'S5_Soil_coef_COS2', 'S5_Soil_coef_SIN2', 'S5_Soil_coef_COS3', 'S5_Soil_coef_SIN3', 'S1_NDFI_coef_INTP', 'S1_NDFI_coef_SLP', 'S1_NDFI_coef_COS', 'S1_NDFI_coef_SIN', 'S1_NDFI_coef_COS2', 'S1_NDFI_coef_SIN2', 'S1_NDFI_coef_COS3', 'S1_NDFI_coef_SIN3', 'S2_NDFI_coef_INTP', 'S2_NDFI_coef_SLP', 'S2_NDFI_coef_COS', 'S2_NDFI_coef_SIN', 'S2_NDFI_coef_COS2', 'S2_NDFI_coef_SIN2', 'S2_NDFI_coef_COS3', 'S2_NDFI_coef_SIN3', 'S3_NDFI_coef_INTP', 'S3_NDFI_coef_SLP', 'S3_NDFI_coef_COS', 'S3_NDFI_coef_SIN', 'S3_NDFI_coef_COS2', 'S3_NDFI_coef_SIN2', 'S3_NDFI_coef_COS3', 'S3_NDFI_coef_SIN3', 'S4_NDFI_coef_INTP', 'S4_NDFI_coef_SLP', 'S4_NDFI_coef_COS', 'S4_NDFI_coef_SIN', 'S4_NDFI_coef_COS2', 'S4_NDFI_coef_SIN2', 'S4_NDFI_coef_COS3', 'S4_NDFI_coef_SIN3', 'S5_NDFI_coef_INTP', 'S5_NDFI_coef_SLP', 'S5_NDFI_coef_COS', 'S5_NDFI_coef_SIN', 'S5_NDFI_coef_COS2', 'S5_NDFI_coef_SIN2', 'S5_NDFI_coef_COS3', 'S5_NDFI_coef_SIN3']

    print('testcoef', testcoef)

    tStart = buildStartEndBreakProb(fit, nSegments, 'tStart')
    testtStart = tStart.bandNames().getInfo() == [
        'S1_tStart', 'S2_tStart', 'S3_tStart', 'S4_tStart', 'S5_tStart']
    print('testtStart', testtStart)

    tEnd = buildStartEndBreakProb(fit, nSegments, 'tEnd')
    testtEnd = tEnd.bandNames().getInfo() == [
        'S1_tEnd', 'S2_tEnd', 'S3_tEnd', 'S4_tEnd', 'S5_tEnd']
    print('testtEnd', testtEnd)

    tBreak = buildStartEndBreakProb(fit, nSegments, 'tBreak')
    testtBreak = tBreak.bandNames().getInfo() == [
        'S1_tBreak', 'S2_tBreak', 'S3_tBreak', 'S4_tBreak', 'S5_tBreak']
    print('testtBreak', testtBreak)

    probs = buildStartEndBreakProb(fit, nSegments, 'changeProb')
    testprobs = probs.bandNames().getInfo() == [
        'S1_changeProb', 'S2_changeProb', 'S3_changeProb', 'S4_changeProb', 'S5_changeProb']
    print('testprobs', testprobs)

    nobs = buildStartEndBreakProb(fit, nSegments, 'numObs')
    testnobs = nobs.bandNames().getInfo() == [
        'S1_numObs', 'S2_numObs', 'S3_numObs', 'S4_numObs', 'S5_numObs']
    print('testnobs', testnobs)
