# API RESPONSE STRUCTURE FROM GOOGLE MAPS DIRECTIONS...
# DATA
# 1 ROUTE (use int index[0])
# 2 LEG, unless waypoint, then 2+ legs
# 3 STEPS in each leg
# 4 Detail for each step
"""
FUTURE PROJECT ENHANCEMENTS, TO DO LIST:

- add docstrings to each function

- how to get bool() to recognize when my string from csv is "FALSE" or "TRUE" or "false" or "true"

- probably need to run it through one user at a time? rather than in batch. that way if a user fails, it's only that user. move onto the next.

- in console, return count of users and progress, etc

- am I looking at UTC or EST times when I send to google  https://developers.google.com/maps/documentation/directions/intro#optional-parameters
need to add computation for this?
best package for timezones: pytz?

- save, read, write data to file io
if i'm saving lists, e.g. list of GPS coords, how to do that in a csv
save in csv the full string of gps coords together, or keep a list of coords in csv to be remanipulated each time the program runs? (latter makes it easier to removes/edit gps coords, or if google changes how they receive syntax)

- Website to sign up/google places api to find the google place id for each user's origin and destination

- use duration in traffic, but be prepared to handle in the event that data is not available

- only 25 waypoints allowed (beyond origin and destination), how to work around?
remove the smallest mileage segments, with the assumption that will affect the routing the least
in jacob's case, it might have made a difference though
test pushing more than 23 waypoints to google

- Geofence to send alert when you leave that address, if between specific hours 

- (nah, just let them pick out the route on a map) option to "fork Into" and "fork out of" a main vein. e.g. a chuck of i-70 will always be part of my route, so compare for me 2-3 options getting onto 70, then again getting off

- Compare the longest street involved and show the street before and after, all in a 3-road description of the route in general. 
Eg Capital, 70, Ronald regan 
"""
import requests
import pprint
import datetime
import time
import csv

# Delete the variable below, and its references, once we go live. Just for easier testing.
send_texts = True
send_texts = input("Send texts (y/n): ")
if send_texts == "y":
    send_texts = True
else:
    send_texts = False

def return_next_week_5pm_in_seconds():

    day_of_week = datetime.datetime.today().weekday()

    if day_of_week in range(0, 5):
        days_to_add = 7
    elif day_of_week in [5, 6]:
        days_to_add = 2

    now = datetime.datetime.now()
    today_5pm_in_seconds = datetime.datetime(now.year, now.month, now.day, 17, 0, 0).timestamp()
    seconds_to_add = days_to_add*24*60*60
    temporary_utc_to_est_conversion = 60*60*4
    future_5pm = int(today_5pm_in_seconds + seconds_to_add - temporary_utc_to_est_conversion)
    return str(future_5pm)


def convert_secs_to_hr_min_string(seconds):

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


def build_api_url(origin, destination, now, ifwaypoints, waypoints=""):

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
        "argument": "AIzaSyCXIqHF9C5CBJrbsHsYBbruIB9TvJ2Ks1M"
    },
    {
        "parameter": "alternatives",    # Only works without intermediate waypoints
        "argument": "false"
    },
    {
        "parameter": "mode",
        "argument": "driving"
    }
]

    url = ""
    for item in url_base_characteristics:
        if item["parameter"] == "":
            url += item["argument"]
        else:
            url += f'&{item["parameter"]}={item["argument"]}'
    
    if now == True and ifwaypoints == False:
        url += "&departure_time=now"
    if now == True and ifwaypoints == True:
        url += "&departure_time=now" + "&waypoints=" + waypoints
    if now == False and ifwaypoints == True:
        url += "&departure_time=" + return_next_week_5pm_in_seconds() + "&waypoints=" + waypoints
    return url


def sift_html(html): # Distill the response.html_instructions to get closer to simply the street name
    writing_tag = False
    recording = False
    tag = ""
    keep_string = ""

    for letter in html:
        if letter == "<":
            recording = False
            writing_tag += 1

        if recording and writing_tag < 1:
            keep_string += letter

        if letter == ">":
            tag += letter
            writing_tag -= 1
            if tag == "<wbr/>":
                keep_string += " / "
            elif tag[0:2] == "</":
                recording = False
            else:
                recording = True
            tag = ""

        if writing_tag:
            tag += letter

    return keep_string



def parse_api_response(request):

    # Collect string of lat/lng from the steps in json response
    latlng = ""
    for leg in request["api_response"]["routes"][0]["legs"]:
        for step in leg["steps"]:
            latlng += "via:" + str(step["start_location"]["lat"]) + "%2C" + str(step["start_location"]["lng"]) + "%7C"
    
    # Add lat/lng string to dictionary
    request["waypoints"] = latlng


    total_distance = 0
    sum_duration = 0
    sum_duration_w_traffic = 0
    print("\n")
    print(f'Route: {request["api_response"]["routes"][0]["summary"]}, {request["type"]}')
    i = 1
    legnum = 1
    rte_index = 0
    # Print summary of legs in the journey
    for leg in request["api_response"]["routes"][rte_index]["legs"]:
        # print(f'Leg {legnum}: {leg["distance"]["text"]} {leg["duration"]["text"]}  (Duration in traffic: {leg["duration_in_traffic"]["text"]}) (<-- Both estimates from metadata)')
        sum_duration_w_traffic += int(leg["duration_in_traffic"]["value"])
        for step in leg["steps"]:
            # print(f'\t{i} | {step["html_instructions"][0:45]} | {step["distance"]["text"]} {step["duration"]["text"]} | ({step["start_location"]["lat"]},{step["start_location"]["lng"]})')
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

# this is where you left off.....
def unpack_request_file(file):
    
    file = csv.DictReader(file)

    for i in file:
        if i["active"]:
            request_list.append(i)


def add_urls_to_requests(request_list):

    for request in request_list:
        # Build list of dictionaries, each dictionary a type of requests to google, with metadata and api response
        url_list = []
        url_list.append({"type": "default", "api_url": build_api_url(request["origin"], request["destination"], True, True, request["waypoints"]), "api_response": "null for now"})
        url_list.append({"type": "best_available", "api_url": build_api_url(request["origin"], request["destination"], True, False, waypoints=""), "api_response": "null for now"})
        # url_list.append({"type": "default_typically", "api_url": build_api_url(request["origin"], request["destination"], False, True, request["waypoints"]), "api_response": "null for now"})
        request["url_list"] = url_list


def suggest_alt_route(default_seconds, best_available_seconds, delta, phone):
    import send_sms
    default = convert_secs_to_hr_min_string(default_seconds)
    best = convert_secs_to_hr_min_string(best_available_seconds)
    delta = convert_secs_to_hr_min_string(delta)

    text_body = f'Save {delta}, your usual route is {default} and a {best} alternative exists.'
    print(text_body)
    if send_texts:
        send_sms.send_sms(phone, text_body)


def suggest_usual_route(default_seconds, best_available_seconds, delta, phone, tolerance_seconds):
    import send_sms
    default = convert_secs_to_hr_min_string(default_seconds)
    best = convert_secs_to_hr_min_string(best_available_seconds)
    delta = convert_secs_to_hr_min_string(delta)
    tolerance = convert_secs_to_hr_min_string(tolerance_seconds)

    text_body = f'Stick to your usual route, at {default}. The best route available is {best}. Your threshold for an alternative is {tolerance}.'
    print(text_body)
    if send_texts:
        send_sms.send_sms(phone, text_body)

request_list = []
with open("requests.csv", "r") as f:
    user_data = f.readlines()

unpack_request_file(user_data)
add_urls_to_requests(request_list)


# Ping Google for each routing scenario, save responses to respective dictionaries
# refactor this
for request in request_list:
    for request in request["url_list"]:
        response = requests.get(request["api_url"])
        # Add error handling to the get request above
        request["api_response"] = response.json()       #? Does this make the request a 2nd time?
        time.sleep(0)           # Just had this to prevent a bad loop sending zillions of requests to google


# Send each json response for parsing and appending to 
for request in request_list:
    for i, request in enumerate(request["url_list"]):
        parse_api_response(request)

# pprint.pprint(request_list[0])

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
