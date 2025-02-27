import json
import boto3

def lambda_handler(event, context):
    try:
        # Extract the intent name from the event
        intent_name = event['currentIntent']['name']
        
        # Handle GreetingIntent
        if intent_name == "GreetingIntent":
            return {
                "dialogAction": {
                    "type": "Close",
                    "fulfillmentState": "Fulfilled",
                    "message": {
                        "contentType": "PlainText",
                        "content": "Hi there, how can I help?"
                    }
                }
            }
        
        # Handle ThankYouIntent
        elif intent_name == "ThankYouIntent":
            return {
                "dialogAction": {
                    "type": "Close",
                    "fulfillmentState": "Fulfilled",
                    "message": {
                        "contentType": "PlainText",
                        "content": "You're welcome!"
                    }
                }
            }
        
        # Handle DiningSuggestionsIntent
        elif intent_name == "DiningSuggestionsIntent":
            # Extract slot values from the event
            slots = event['currentIntent']['slots']
            location = slots['Location']
            cuisine = slots['Cuisine']
            dining_time = slots['DiningTime']
            number_of_people = slots['NumberOfPeople']
            email = slots['Email']
            
            # Check if any slot is missing
            if not location or not cuisine or not dining_time or not number_of_people or not email:
                
                missing_slots = []
                if not location:
                    missing_slots.append("Location")
                if not cuisine:
                    missing_slots.append("Cuisine")
                if not dining_time:
                    missing_slots.append("DiningTime")
                if not number_of_people:
                    missing_slots.append("NumberOfPeople")
                if not email:
                    missing_slots.append("Email")
                
                return {
                    "dialogAction": {
                        "type": "ElicitSlot",
                        "intentName": "DiningSuggestionsIntent",
                        "slots": slots,
                        "slotToElicit": missing_slots[0],  # Prompt for the first missing slot
                        "message": {
                            "contentType": "PlainText",
                            "content": f"Please provide the {missing_slots[0].lower()}."
                        }
                    }
                }
            

            sqs = boto3.client('sqs')
            queue_url = 'https://sqs.us-east-1.amazonaws.com/390403884924/DiningQ'
            message_body = {
                'Location': location,
                'Cuisine': cuisine,
                'DiningTime': dining_time,
                'NumberOfPeople': number_of_people,
                'Email': email
            }
            sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(message_body))
            
            # Respond to the user
            return {
                "dialogAction": {
                    "type": "Close",
                    "fulfillmentState": "Fulfilled",
                    "message": {
                        "contentType": "PlainText",
                        "content": "Thank you! We have received your request and will notify you via email with restaurant suggestions."
                    }
                }
            }
        
        # Handle unknown intents
        else:
            return {
                "dialogAction": {
                    "type": "Close",
                    "fulfillmentState": "Failed",
                    "message": {
                        "contentType": "PlainText",
                        "content": "Sorry, I didn't understand that."
                    }
                }
            }
    
    except KeyError as e:
        # Handle missing keys in the event object
        return {
            "dialogAction": {
                "type": "Close",
                "fulfillmentState": "Failed",
                "message": {
                    "contentType": "PlainText",
                    "content": f"An error occurred: {str(e)}. Please check the event structure."
                }
            }
        }