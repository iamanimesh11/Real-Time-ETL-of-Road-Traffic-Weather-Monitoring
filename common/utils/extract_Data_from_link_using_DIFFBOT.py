import json
import re
import google.generativeai as genai
import requests
import os

# extract google search links of query from google cloud search
from googleapiclient.discovery import build
api_key="AIzaSyBxGGL8Gs3klPnmkh7wosS-yS1bl5YyJkM"
cse_id="50dce64271acf4015"

def google_Search(query,api_key,cse_id):
    service = build("customsearch","v1",developerKey=api_key)
    res = service.cse().list(q=query,cx=cse_id).execute()
    return res['items']

query="congestion in Gaur chawk"
google_results=google_Search(query,api_key,cse_id)
google_search_links=[]
for i in google_results:
    google_search_links.append([i['title'],i['link']])


# providing all link to gemini and get most relatable link
google_Search_link_String="[ "+",".join([f'"{item[0]},"{item[1]}"' for item in google_search_links])
print(google_Search_link_String)

genai_API="AIzaSyCuWhC9Wx80HDB7bOf1R_-yy1P3z7PiKlw"
genai.configure(api_key=genai_API)
model=genai.GenerativeModel(model_name="gemini-1.5-flash")

keyword=" noida extension gaur chawk congestion"
prompt_Text=f"You are provided a list of titles and their corresponding links in the format:  [Title 1: Link 1, Title 2: Link 2], ... .Please evaluate which title from the list is the single most relevant for the search query """"why congestion at Gaur chawk noida extension."""" Provide only one link of the most relevant title(s). If none are suitable, respond with ""No relevant link found."""
foramtted_String= prompt_Text+" "+google_Search_link_String
response=model.generate_content(foramtted_String)
results_links=re.findall(r'(https?://\S+)',response.text)
print("TTTTttttt")

# get data from link using diffbot_api

diffbot_api="4666a87d2a4037b7fc45365717575057"
base_url="https://api.diffbot.com/v3/article"
def extract_content(url):
    try:
        params={
            "token": diffbot_api,
            "url":url,
        "fields": "title,text,sentiment,entities"
        }
        res=requests.get(base_url,params=params,verify=False)
        return res.json()

    except Exception as e:
        return {"error": str(e)}

genai_result_links=[extract_content(link) for link in results_links]
for data in genai_result_links:
    final_text=data.get("objects",[{}])[0].get("text","no content found")

print(final_text)

# provide extracted content to gemini to get summary

response=model.generate_content("pleease provide a concise, summary of the below text: "+ final_text)
Final_message_From_AI =response.text


