# classification.py
import math
import random
import ee

ee.Initialize()

# /**
#  * Subset training data into random training and testing data
#  * Data is subset proportionally for each land cover class
#  * @param {ee.FeatureCollection} trainingData training data
#  * @param {float} trainProp proportion of data to withhold for training
#  * @param {number} seed seed for random selection of subset
#  * @param {string} classProperty property containing the input class
#  * @returns {ee.FeatureCollection} training data with 'train' attribute where 1=training, 0=testing
#  */
def subsetTraining(trainingData, trainProp, seed, classProperty):

    classCounts = ee.Dictionary(trainingData.aggregate_histogram(classProperty))
    classes = classCounts.keys()
    def subset(c):
        subset = trainingData.filterMetadata(classProperty, 'equals',ee.Number.parse(c))
        #//  Withhold a selection of training data
        trainingSubsetWithRandom = subset.randomColumn('random',seed).sort('random')
        indexOfSplit = trainingSubsetWithRandom.size().multiply(trainProp).int32()
        numberOfTrain = trainingSubsetWithRandom.size().subtract(indexOfSplit).int32()
        subsetTest = ee.FeatureCollection(trainingSubsetWithRandom.toList(indexOfSplit)).map(lambda feat : feat.set('train', 0))
        
        subsetTrain = ee.FeatureCollection(trainingSubsetWithRandom.toList(numberOfTrain, indexOfSplit)).map(lambda feat : feat.set('train', 1))
        return ee.Algorithms.If(subset.size().gt(10),
            subsetTest.merge(subsetTrain),
            subset.map(lambda feat : feat.set('train', 1))
        )
    subsets = classes.map(subset)
    return ee.FeatureCollection(subsets).flatten()







# # /**
# # * Calculate accuracy metrics using a subset of the training data
# # * @param {ee.FeatureCollection} trainingData training data
# # * @param {ee.Image} imageToClassify ccdc coefficient stack to classify
# # * @param {array} predictors list of predictor ables as strings
# # * @param {array} bandNames list of band names to classify
# # * @param {array} ancillary list of ancillary predictor data
# # * @param {ee.Classifier} classifier earth engine classifier with parameters
# # * @param {string} [classProperty='LC_Num'] attribute name with land cover label
# # * @param {number} [seed='random'] seed to use for the random column generator
# # * @param {float} [trainProp=.4] proportion of data to use subset for training
# # * @returns {ee.ConfusionMatrix} a confusion matrix as calculated by the train/test subset
# # */
# def accuracyProcedure(trainingData, imageToClassify, predictors, bandNames, 
#     ancillary, classifier, classProperty, seed=None, trainProp):
#     if seed is None:
#         seed = random.randint(0,1000)
#     trainProp =  .4 
#     classProperty = 'LC_Num'
#     trainingData = trainingData.randomColumn('random',seed).sort('random')
#     trainingData = subsetTraining(trainingData, trainProp, seed, classProperty) 
#     testSubsetTest = trainingData.filterMetadata('train','equals',0)

#   testSubsetTrain = trainingData.filterMetadata('train','equals',1)

#   inputList = getInputFeatures(1, imageToClassify, predictors, bandNames, ancillary)
#   inputFeatures = ee.List(inputList).get(0)

#     // inputFeatures = inputList[0]

#   // Train the classifier
#   trained = classifier.train({
#     features: testSubsetTrain,
#     classProperty: classProperty,
#     inputProperties: inputFeatures
#   })
#   classified = testSubsetTest.classify(trained)
#   confMatrix = classified.errorMatrix(classProperty, 'classification')
#   // return [confMatrix, trained]
#   return confMatrix

# }