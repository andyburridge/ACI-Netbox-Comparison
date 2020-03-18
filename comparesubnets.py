import requests
import json
import ipaddress


# Variable declarations
inputSummary = "10.49.0.0/16"

# Subnets that are either not on ACI, or are handled in a different way (DHCP pools, etc)
nonACISubnets = []


# List containing all the endpoints that are on the ACI fabric but not showing as active.  For example; ASA standby addresses.
unReachableEndpointsACI = []

# Variables used for working with Netbox API
apiBaseUrl = "https://<netbox>/api"

headers = {  
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Authorization": "<token>"
}

# Variables used for working with ACI API
aciBaseURL = "https://<aci>"

username = ""
password = ""

# Function declarations

def getNetboxIPs():
	# Query Netbox for a full list of active IP addresses across all sites:
	# 'status = active' gives all IPs marked as 'active'.  'limit = 0' returns all, default only returns 50
	# 'resp' - contains the full .json response
	# 'ipAddressCount' - contains the number of active IP addresses
    resp = requests.get(apiBaseUrl + "/ipam/ip-addresses/?status=active&limit=0", headers=headers, verify=False).json()
    ipAddressCount = resp["count"]
    
    jsonReults = resp["results"]
    counter = 0
    netboxIPs = []
    summary = ipaddress.ip_network(inputSummary)

    while counter < ipAddressCount:
        inSub = False
        inBadSub = False
        endpointPrefix = jsonReults[counter]["address"]
        endpointList = endpointPrefix.split("/")
        endpoint = endpointList[0]
        endpoint = ipaddress.ip_network(endpoint)
        
        if endpoint.subnet_of(summary):
            netboxIPs.append(str(endpoint))
            
        counter+=1

    return netboxIPs   


def getACIEndpoints():
	# Query ACI for a full list of active endpoints on the fabric
	# Login to APIC
    loginURL = "/api/aaaLogin.json"
    login_data = {"aaaUser":{"attributes":{"name":username, "pwd":password}}}
    resp = requests.post(aciBaseURL + loginURL, data=json.dumps(login_data), verify=False).json()['imdata'][0]

    # Convert response to json and extract auth token to use as cookie in following request
    respJSON = json.dumps(resp)
    respJSONDict = json.loads(respJSON)
    token = respJSONDict["aaaLogin"]["attributes"]["token"]
    cookie = {'APIC-cookie':token}

    if 'error' in resp:
        raise Exception(resp['error']['attributes']['text'])


    # Query APIC for all endpoint IPs. 
    # This gives the IP associated to an endpoint attached to the fabric, but doesn't include the ACI default gateways, or L3 outs.
    # This is requried in addition to the fvIP object, as sometimes this object isn't created in the tree.
    endpointQuery = '/api/node/class/fvCEp.json'
    resp = requests.get(aciBaseURL + endpointQuery, cookies=cookie, verify=False).json()

    ipAddressCount = int(resp["totalCount"])
    aciIPs = []
    counter = 0
    summary = ipaddress.ip_network(inputSummary)

    while counter < ipAddressCount:
        endpoint = ipaddress.ip_network(resp['imdata'][counter]["fvCEp"]["attributes"]["ip"])
        if endpoint.subnet_of(summary):
            aciIPs.append(str(endpoint))
        counter+=1


    # This is required in addition to the client endpoint object, to cater for the scenario where an endpoint has more than 1 IP
    # address associated to its MAC (e.g. an F5 with multiple VIPs).  Querying the endpoint doesn't return all the IPs, we have 
    # to query the IP objects underneath the endpoint.
    endpointQuery = '/api/node/class/fvIp.json'
    resp = requests.get(aciBaseURL + endpointQuery, cookies=cookie, verify=False).json()

    ipAddressCount = int(resp["totalCount"])
    counter = 0
    summary = ipaddress.ip_network(inputSummary)

    while counter < ipAddressCount:
        endpoint = ipaddress.ip_network(resp['imdata'][counter]["fvIp"]["attributes"]["addr"])
        if endpoint.subnet_of(summary):
            aciIPs.append(str(endpoint))
        counter+=1


    # Query APIC for all vNIC IPs. 
    # This is required in addition to the client endpoints and IPs, to cater for the scenario where an endpoint is learned only
    # by its VMM association, and not via the fabric itself.
    endpointQuery = '/api/node/class/compVNic.json'
    resp = requests.get(aciBaseURL + endpointQuery, cookies=cookie, verify=False).json()

    ipAddressCount = int(resp["totalCount"])
    counter = 0
    summary = ipaddress.ip_network(inputSummary)

    while counter < ipAddressCount:
        endpoint = ipaddress.ip_network(resp['imdata'][counter]["compVNic"]["attributes"]["ip"])
        if endpoint.subnet_of(summary):
            aciIPs.append(str(endpoint))
        counter+=1


    # Query APIC for all bridge domain subnet IPs.
    # These are the subnet default gateways provided by ACI.
    endpointQuery = '/api/node/class/fvSubnet.json'
    resp = requests.get(aciBaseURL + endpointQuery, cookies=cookie, verify=False).json()

    ipAddressCount = int(resp["totalCount"])
    counter = 0

    while counter < ipAddressCount:
        endpointPrefix = resp['imdata'][counter]["fvSubnet"]["attributes"]["ip"]
        endpointList = endpointPrefix.split("/")
        endpoint = endpointList[0]
        endpoint = ipaddress.ip_network(endpoint)
        if endpoint.subnet_of(summary):
            aciIPs.append(str(endpoint))
        counter+=1


    # Query APIC for all L3 Out IPs.
    endpointQuery = '/api/node/class/l3extMember.json'
    resp = requests.get(aciBaseURL + endpointQuery, cookies=cookie, verify=False).json()

    ipAddressCount = int(resp["totalCount"])
    counter = 0

    while counter < ipAddressCount:
        endpointPrefix = resp['imdata'][counter]["l3extMember"]["attributes"]["addr"]
        endpointList = endpointPrefix.split("/")
        endpoint = endpointList[0]
        endpoint = ipaddress.ip_network(endpoint)
        if endpoint.subnet_of(summary):
            aciIPs.append(str(endpoint))
        counter+=1


    # Query APIC for all L3 Out router IDs.
    endpointQuery = '/api/node/class/l3extRsNodeL3OutAtt.json'
    resp = requests.get(aciBaseURL + endpointQuery, cookies=cookie, verify=False).json()

    ipAddressCount = int(resp["totalCount"])
    counter = 0

    while counter < ipAddressCount:
        endpointPrefix = resp['imdata'][counter]["l3extRsNodeL3OutAtt"]["attributes"]["rtrId"]
        endpointList = endpointPrefix.split("/")
        endpoint = endpointList[0]
        endpoint = ipaddress.ip_network(endpoint)
        if endpoint.subnet_of(summary):
            aciIPs.append(str(endpoint))
        counter+=1

    return aciIPs


def compareLists(list1, list2): 
    return (list((set(list1) - set(list2)) - set(unReachableEndpointsACI)))


def main():
    netboxList = getNetboxIPs()
    aciList = getACIEndpoints()

    netboxBadList = []
    aciBadList = []

    # Compare lists of IPs to the subnets that we don't want to check, due to discrepancies on reporting.
    for ip in netboxList:
        endpoint = ipaddress.ip_network(ip)
        for subnet in nonACISubnets:
            badSummary = ipaddress.ip_network(subnet)
            if endpoint.subnet_of(badSummary):
                netboxBadList.append(str(ip))

    for ip in aciList:
        endpoint = ipaddress.ip_network(ip)
        for subnet in nonACISubnets:
            badSummary = ipaddress.ip_network(subnet)
            if endpoint.subnet_of(badSummary):
                aciBadList.append(str(ip))


    # Get the difference between the lists, minus the IPs from the subnets we don't care about.     
    diffNbxACI = compareLists(netboxList, aciList)
    cleanNbxACI = compareLists(diffNbxACI, netboxBadList)
    print ("IPs in Netbox, but not in ACI: " + str(cleanNbxACI))

    diffACINbx = compareLists(aciList, netboxList)
    cleanACINbx = compareLists(diffACINbx, aciBadList)
    print ("IPs in ACI, but not in Netbox: " + str(cleanACINbx))

    #getMerakiClient()



if __name__ == '__main__':
    main()

