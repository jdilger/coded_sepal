# testing_dicts.py

from coded_python.data.testing.samples import *
from coded_python.data.testing.regions import *

not_prepped = {
    'start': '2018-01-01',
    'end': '2020-12-31',
    'prepTraining': True,
    'studyArea': test_study_area().region,
    'training': python_coded().raw
}

prepped = {
    'start': '2018-01-01',
    'end': '2020-12-31',
    'prepTraining': False,
    'studyArea': test_study_area().region,
    'training': python_coded().prepped_samples
}