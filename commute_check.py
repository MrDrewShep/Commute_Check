
import requests
import pprint
import datetime
import time
import csv
from keys import google_maps_directions_key as key_gmd

# Code block below is helpful while still tinkering with the app. Eventually can be deleted, once the app runs automatically.
send_texts = True
send_texts = input("Send texts (y/n): ")
if send_texts == "y":
    send_texts = True
else:
    send_texts = False


def convert_secs_to_hr_min_string(seconds):
    """Google converses in seconds, for departure time and duration of routes. This converts it to a readable format of hours/minutes."""

    duration_string = ""

    duration_hrs = int((seconds/60) // 60)
    duration_minutes = int((seconds/60) % 60)

    if duration_hrs > 0:
        duration_string += f'{duration_hrs}'
        if duration_hrs == 1:
            duration_string += " hr "
        else:
            duration_string += " hrs "
    duration_string += f'{duration_minutes} min'

    return duration_string


def build_api_url(origin, destination, waypoints=""):
    """Builds the respective URLs, per user, to send to Google and compare responses.""" 

    url_base_characteristics = [
    {
        "parameter": "",
        "argument": "https://maps.googleapis.com/maps/api/directions/json?"
    },
    {
        "parameter": "origin",
        "argument": origin
    },
    {
        "parameter": "destination",
        "argument": destination
    },
    {
        "parameter": "key",
        "argument": key_gmd
    },
    {
        "parameter": "alternatives",    # Only works without intermediate waypoints
        "argument": "false"
    },
    {
        "parameter": "mode",
        "argument": "driving"
    },
    {
        "parameter": "departure_time",
        "argument": "now"
    },
    {
        "parameter": "waypoints",
        "argument": waypoints
    }
]

    url = ""
    for item in url_base_characteristics:
        if item["parameter"] == "":
            url += item["argument"]
        else:
            url += f'&{item["parameter"]}={item["argument"]}'
    
    return url


def parse_api_response(request):
    """Take each Google API JSON response and parse the response for data."""

    # I used this code block the first time a request was sent, to capture the lat/lon waypoints involved in the route. They are manually saved into the requests.csv file as the "usual"/preferred route.
    latlng = ""
    for leg in request["api_response"]["routes"][0]["legs"]:
        for step in leg["steps"]:
            latlng += "via:" + str(step["start_location"]["lat"]) + "%2C" + str(step["start_location"]["lng"]) + "%7C"
    request["waypoints"] = latlng


    total_distance = 0
    sum_duration = 0
    sum_duration_w_traffic = 0
    print("\n")
    print(f'Route: {request["api_response"]["routes"][0]["summary"]}, {request["type"]}')
    i = 1
    legnum = 1
    rte_index = 0

    for leg in request["api_response"]["routes"][rte_index]["legs"]:
        sum_duration_w_traffic += int(leg["duration_in_traffic"]["value"])
        for step in leg["steps"]:
            i += 1
            total_distance += int(step["distance"]["value"])
            sum_duration += int(step["duration"]["value"])
        legnum += 1

    # Convert cumluative seconds into string of x hrs y min
    duration = convert_secs_to_hr_min_string(sum_duration)
    duration_w_traffic = convert_secs_to_hr_min_string(sum_duration_w_traffic)
    request["duration"] = sum_duration
    request["duration_str"] = duration
    request["duration_w_traffic"] = sum_duration_w_traffic
    request["duration_w_traffic_str"] = duration_w_traffic
    print(f"Total: {round(total_distance/1607, 1)} mi, {duration}, {duration_w_traffic} with traffic")


def unpack_request_file(file):
    """Opens the file of users. If opted-in, adds that user to a list of dictionaries. Each dictinoary representing the data from the file, and a future "request" to be made to Google Maps Directions API."""
    
    file = csv.DictReader(file)

    for i in file:
        if bool(int(i["active"])):
            request_list.append(i)


def add_urls_to_requests(request_list):
    """For each user-request in the list, adds a dictionary entry which is a list of URLs and a placeholder for their future JSON responses."""

    for request in request_list:
        url_list = []
        url_list.append({"type": "default", "api_url": build_api_url(request["origin"], request["destination"], request["waypoints"]), "api_response": None})
        url_list.append({"type": "best_available", "api_url": build_api_url(request["origin"], request["destination"], waypoints=""), "api_response": None})
        request["url_list"] = url_list


def suggest_alt_route(default_seconds, best_available_seconds, delta, phone):
    """Sends an SMS suggesting the user take an alternate route."""

    import send_sms
    default = convert_secs_to_hr_min_string(default_seconds)
    best = convert_secs_to_hr_min_string(best_available_seconds)
    delta = convert_secs_to_hr_min_string(delta)

    text_body = f'Save {delta}, your usual route is {default} and a {best} alternative exists.'
    print(text_body)
    if send_texts:
        send_sms.send_sms(phone, text_body)


def suggest_usual_route(default_seconds, best_available_seconds, delta, phone, tolerance_seconds):
    """Sends an SMS suggesting the user take their usual route. Note: This is for testing purposes. Eventually the suggestion of a user's "usual" route would be indicated by a non-notificaiton."""

    import send_sms
    default = convert_secs_to_hr_min_string(default_seconds)
    best = convert_secs_to_hr_min_string(best_available_seconds)
    delta = convert_secs_to_hr_min_string(delta)
    tolerance = convert_secs_to_hr_min_string(tolerance_seconds)

    text_body = f'Stick to your usual route, at {default}. The best route available is {best}. Your threshold for an alternative is {tolerance}.'
    print(text_body)
    if send_texts:
        send_sms.send_sms(phone, text_body)

# Starts a list of user-requests. Each of which will follow with multiple calls to Google Maps Directions for comparison and analysis.
request_list = []
with open("requests.csv", "r") as f:
    user_data = f.readlines()

unpack_request_file(user_data)
add_urls_to_requests(request_list)

# For each user request, for each type of request for comparison, call Google for each routing scenario, save responses to respective dictionaries.
for request in request_list:
    for request in request["url_list"]:
        response = requests.get(request["api_url"])
        request["api_response"] = response.json()

# Send each JSON response for parsing.
for request in request_list:
    for route_type in request["url_list"]:
        parse_api_response(route_type)

# For each user-request, determine whether a best-available route improves the usual route beyond the user's defined threshold. Sends SMS if necessary.
for request in request_list:
    phone = "+1" + request["phone"]
    tolerance_min = int(request["route_improvement_tolerance_absolute"])
    tolerance_sec = tolerance_min*60
    for type_request in request["url_list"]:
        if type_request["type"] == "default":
            default_duration_w_traffic = type_request["duration_w_traffic"]
        if type_request["type"] == "best_available":
            best_available_duration_w_traffic = type_request["duration_w_traffic"]
    
    delta = default_duration_w_traffic - best_available_duration_w_traffic
    print(f'\n{phone} with tolerance of {tolerance_min} min, usual route is {round(default_duration_w_traffic/60,1)} min and a route exists at {round(best_available_duration_w_traffic/60,1)} min. A difference of {round(delta/60,1)} min.')
    if delta > tolerance_sec:
        print("Suggest an alt route")
        suggest_alt_route(default_duration_w_traffic, best_available_duration_w_traffic, delta, phone)
    else:
        print("Do not suggest alt route")
        suggest_usual_route(default_duration_w_traffic, best_available_duration_w_traffic, delta, phone, tolerance_sec)
