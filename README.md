# Grab text from images and convert them to an audio file.

## Install

1. install Python 3
2. create a virtual env: `python -m venv venv`
3. activate the virtual env: `source venv/bin/activate`
4. install requirements: `python -m pip install -r requirements.txt`

## Use

1. make sure to have an AWS profile setup with access to `s3`, `textract` and `polly`
2. add images in the `pages` folder, named in alphabetical order to be read
3. run the script: `python main.py AWS-PROFILE AWS-BUCKET PREFIX
4. check the generated audio file in the target bucket
