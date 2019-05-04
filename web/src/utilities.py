import json

def printJSON(data, indentvalue=2):
    print(json.dumps(json.loads(data), indent=indentvalue, sort_keys=True))