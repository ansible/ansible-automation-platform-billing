#!/bin/sh

cd azure_billing
python3 manage.py test --settings=test_settings tests
