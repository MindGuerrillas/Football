import json
import constant as const 
import unicodedata

def printJSON(data, indentvalue=2):
    print(json.dumps(json.loads(data), indent=indentvalue, sort_keys=True))

def debuggingPrint(output):
    if const.VERBOSE:
        print (output + "\n")

def strip_accents(text):

    try:
        text = unicode(text, 'utf-8')
    except NameError: # unicode is a default on python 3 
        pass

    text = unicodedata.normalize('NFD', text)\
           .encode('ascii', 'ignore')\
           .decode("utf-8")

    return str(text)