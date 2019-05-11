import json
import constant as const 

def printJSON(data, indentvalue=2):
    print(json.dumps(json.loads(data), indent=indentvalue, sort_keys=True))

def debuggingPrint(output):
    if const.VERBOSE:
        print (output + "\n")

