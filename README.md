# ACI-Netbox-Comparison

## Description 
Using the Netbox REST API to query the intended state of the network, and the ACI REST API to query the active state of the fabric, compare the two in order to ensure data validity.		

Python 3.6


## Prerequisites

requests, json, ipaddress


## Usage
(Improve process flow, for now these are just variables in the script)

- 'inputSummary' defines subnet for which we wish to run the comparison.
- 'headers' contains netbox API token
- 'apiBaseURL' defines the Netbox API URL
- 'aciBaseURL' defines the ACI API URL
- 'username/password' contains the credentials for authenticating to ACI 


## Author

Andrew Burridge
