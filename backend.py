
from multion.client import MultiOn
from openai import OpenAI
from flask import Flask, request
import os
from flask_cors import CORS
from geopy.geocoders import Photon

from dotenv import load_dotenv
map_system_prompt = """
You are an assistant that will take the output of a web navigation task as an input and figure out
if the answer for the task involves different locations with addresses that can be mapped

Complete set of inputs:
1) Initial user prompt
2) Text of web navigation task output

Your task is to determine whether the web naviagtion task output contains location data. If no
location data is in the output, output "NOT APPLICABLE". If, based on the user's prompt, you think that
the web navigation task should contain a list of addresses but doesn't, output "MORE INFO" followed by a response of what you feel is missing from
the task output. Otherwise, output a list of all addresses in the output. Ensure that all addresses are complete with city, state, and zip code. If any of these fields are missing, please ask for more info about all of the addresses which are missing these fields.

Once again, responses should be in a specific format. It is very important that you follow this exact format, either

1) "NOT APPLICABLE"
2) "MORE INFO" + <<<Reason for needing more information about addresses>>>
3) 
<<<Address 1>>>
<<<Short Description of Address 1>>>
<<<Address 2>>>
<<<Short Description of Address 2>>>
...
<<<Address N>>>
<<<Short Description of Address N>>>

For option 3, follow this exact format. Only output valid addresses, and DO NOT HAVE ANY EXTRA NEW LINES
"""

load_dotenv()
temperature = 0
app = Flask(__name__)
# CORS(app, resources={r"/*": {"origins": "http://localhost:5173"}})
CORS(app)
client_multion = MultiOn(api_key=os.getenv("MULTION_API_KEY"))

client = OpenAI()

create_response = client_multion.sessions.create(
    url="www.google.com"
  )
step_response = ""
session_id = create_response.session_id

@app.route("/get_landmarks", methods=['POST'])
def get_landmarks():
    user_prompt = request.json.get('question')
    status = "CONTINUE"
    
    while status == "CONTINUE":
        step_response = client_multion.sessions.step(
            session_id=session_id,
            cmd=user_prompt,
            include_screenshot=True
        )
        status = step_response.status
        if(status == "ASK_USER"):
            return {"response": step_response.message, "points": []}

    while True:
        completion = client.chat.completions.create(
          model="gpt-4o-mini",
          messages=[{"role": "system", "content": map_system_prompt}, {"role":"user", "content": f"User Prompt: {user_prompt} Task Output: {step_response.message}"}],
          temperature=temperature,
        )

        response = completion.choices[0].message.content
        print(response)
        if("NOT APPLICABLE" in response):
            return {"response": step_response.message, "points": []}
        elif("MORE INFO" in response):
          status = "CONTINUE"
          while status == "CONTINUE":
            step_response = client_multion.sessions.step(
                session_id=session_id,
                cmd=response,
                include_screenshot=True
            )
            status = step_response.status
            print(step_response.message)
            print(step_response.screenshot)
            print(step_response.status)
            if(status == "ASK_USER"):
                return {"response": step_response.message, "points": []}

        else:
          addresses = response.split("\n")
          geolocator = Photon(user_agent="geoapiExercises")
          points = []
          for i in range(0,len(addresses),2):
            location = geolocator.geocode(addresses[i])
            if location:
                points.append({"loc": [location.latitude, location.longitude], "desc": addresses[i+1]})
            else:
                print("Address not found")
          return {"response": step_response.message, "points": points}

if __name__ == '__main__':
    app.run(debug=True)
