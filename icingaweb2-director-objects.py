#!/usr/bin/env python3
# copyright: B1 Systems GmbH <info@b1-systems.de>, 2019
# license:   GPLv3+, http://www.gnu.org/licenses/gpl-3.0.html
# author:    Christian Schneemann <schneemann@b1-systems.de>

import requests
import argparse
import json, yaml
import sys
import getpass

params = argparse.ArgumentParser(description="Create objects in icingaweb2-director from json/yaml file")
params.add_argument('--objectsfile', '-i', required=True, help="json/yaml file with list of objects.")
params.add_argument('--user', '-u', required=True, help="API user who can create objects.", default="")
params.add_argument('--url', required=True, help="API URL.", default="")
params.add_argument('--path', required=False,  default="/icingaweb2/director",
        help="Path to API, needed if not http(s)://example.com/icingaweb2/director.")
params.add_argument('--password', '-p', required=False, help="Password for API user.", default="")
params.add_argument('--askpass', required=False, action='store_const', const=True, help="Ask for password.")
params.add_argument('--deploy', '-d', required=False, action='store_const', const=True, help="Deploy config in director at the end.")
params.add_argument('--action', required=False, default='create' help="API URL.", default="")

args = params.parse_args()
filename = args.objectsfile
api_user = args.user
api_passwd = args.password

if args.askpass:
    try:
        p = getpass.getpass()
    except Exception as err:
        print('Error:', err)
        sys.exit(2)
    else:
        api_passwd = p

api_address = args.url+args.path
deploy = args.deploy
action = args.action
if (action != 'create') or (action != 'delete'):
  print("Invalid action, allowed values: create and delete")

############### functions: ######################
def get_templates(obj_type):
    request_url = api_address+"/"+obj_type+"s/templates"
    r = call_api(request_url, None)
    templates = [ ]
    if r.status_code == 200:
        for o in r.json()['objects']:
            templates.append(o['object_name'])
    else:
        print(r.text)
        sys.exit(2)
    return templates

def get_applyrules(obj_type):
    request_url = api_address+"/"+obj_type+"applyrules"
    r = call_api(request_url, None)
    rules = [ ]
    if r.status_code == 200:
        for o in r.json()['objects']:
            rules.append({"object_name": o['object_name'], "id": o['id']})
    else:
        print(r.text)
        sys.exit(2)
    return rules

# check if object exists, if yes add ?name=$hostname...
# if its a rule we have to look for the id to change it
# for templates we have to look into all templates if it already exists
def does_object_exist(obj_type, obj):
    if obj['object_type'] == 'template':
        if obj['object_name'] in get_templates(obj_type):
            print("Template-Object \"{}\" of type \"{}\" already exists...".format(obj['object_name'], obj_type))
            return 1
        else:
            print("Template-Object \"{}\" of type \"{}\" does not exist yet...".format(obj['object_name'], obj_type))
            return 0
    path = "/"+obj_type+"?name="+obj['object_name']
    request_url = api_address+path
    r = call_api(request_url, None)
    if str(r.status_code) != '404':
        print("Object \"{}\" of type \"{}\" already exists...".format(obj['object_name'], obj_type))
        return 1
    else:
        print("Object \"{}\" of type \"{}\" does not exist yet...".format(obj['object_name'], obj_type))
        return 0

def get_apply_rule_id(obj_type, object_name):
    rules = get_applyrules(obj_type)
    found_id = ""
    for rule in rules:
        if rule['object_name'] == obj['object_name']:
            found_id = rule['id']
    return found_id

def build_request_url(object_type, obj):
    # check if object already exists
    if obj['object_type'] == 'apply':
        found_id = get_apply_rule_id(obj_type, obj['object_name'])
        if found_id != "":
            print("Object \"{}\" of type \"{}\" already exists with id {}...".format(obj['object_name'], obj_type, found_id))
            request_url = api_address+"/"+obj_type+"?id="+found_id
        else:
            print("Object \"{}\" of type \"{}\" does not exist yet...".format(obj['object_name'], obj_type))
            request_url = api_address+"/"+obj_type
    else:
        if does_object_exist(obj_type, obj):
            request_url = api_address+"/"+obj_type+"?name="+obj['object_name']
        else:
            request_url = api_address+"/"+obj_type

    return request_url

def create_update_object(obj_type, obj):
    request_url = build_request_url(obj_type, obj)
    call_api(request_url, obj, 'POST')

def delete_object(obj_type, obj):
    if does_object_exist(obj_type, obj):
        request_url = build_request_url(obj_type, obj)
        call_api(request_url, obj, 'DELETE')
    else:
        print("object does not exit..")

def deploy_config():
    r = call_api(api_address+"/config/deploy")
    if r.status_code == 200:
        print("Deployed")
    else:
        print("Error")

def call_api(url, data = None, method = 'POST'):
    headers = {
            'Accept': 'application/json',
            'X-HTTP-Method-Override': method
            }
    r = requests.post(url,
            headers=headers,
            auth=(api_user, api_passwd),
            data=json.dumps(data),
            verify=None
            )
    return r


############### :functions ######################


with open(filename, 'r') as objectsfile:
    data = yaml.load(objectsfile)

failed = False
for obj_type in ('timeperiod', 'command', 'host', 'service' ):
    if obj_type+"s" in data:
        for obj in data[obj_type+"s"]:
            if type(obj) is dict:
                r = create_update_object(obj_type, obj)
                if (r.status_code == 200):
                    print("Object changed")
                elif (r.status_code == 201):
                    print("created")
                elif (r.status_code == 304):
                    print("Object not changed")
                else:
                    failed = True
                    print(r.text)
                    r.raise_for_status()

if (failed == False) and (deploy == True):
    deploy_config()
