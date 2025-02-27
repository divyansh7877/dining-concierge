import json
import boto3
import logging
import requests


# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
sqs = boto3.client('sqs')
dynamodb = boto3.resource('dynamodb')
ses = boto3.client('ses')

# Get configuration from environment variables
QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/390403884924/DiningQ'
DYNAMODB_TABLE = 'yelp-restaurants'
SENDER_EMAIL = 'divyansh.agarwal@nyu.edu'



def lambda_handler(event, context):
    """
    Lambda function that processes restaurant recommendations from an SQS queue
    
    Args:
        event (dict): Lambda event data
        context (object): Lambda context
        
    Returns:
        dict: Response containing status and message details
    """
    try:
        # Receive message from SQS queue
        response = sqs.receive_message(
            QueueUrl=QUEUE_URL,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=5,
            AttributeNames=['All'],
            MessageAttributeNames=['All']
        )
        
        # Check if any messages were received
        if 'Messages' in response:
            message = response['Messages'][0]
            receipt_handle = message['ReceiptHandle']
            
            # Parse message body
            message_body = json.loads(message['Body'])
            logger.info(f"Message received: {message_body}")
            
            # Extract customer preferences
            location = message_body.get('Location')
            cuisine = message_body.get('Cuisine')
            dining_time = message_body.get('DiningTime')
            number_of_people = message_body.get('NumberOfPeople')
            email = message_body.get('Email')
            

            # Search for restaurant recommendations in ElasticSearch
            restaurant_ids = search_restaurants(cuisine)
            logger.info(f"Restaurants fetched from ES")

            if not restaurant_ids:
                logger.warning(f"No restaurants found for cuisine: {cuisine}")
                send_no_results_email(email, cuisine)
            else:
                # Get detailed restaurant information from DynamoDB
                restaurants = get_restaurant_details(restaurant_ids)
                logger.info(f"Restaurants fetched from DB")
                # Send email with recommendations
                send_recommendation_email(email, restaurants, cuisine, dining_time, number_of_people)
                logger.info(f"Restaurants sent via email")
            # Delete the processed message from the queue
            sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt_handle)
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Message successfully processed',
                    'messageBody': json.dumps(message_body)
                })
            }
        else:
            logger.info("No messages available in the queue")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'No messages available in the queue'})
            }
            
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': f'Error processing message: {str(e)}'})
        }

def search_restaurants(cuisine, limit=5):
    """
    Search for restaurants by cuisine type in ElasticSearch
    
    Args:
        cuisine (str): Type of cuisine to search for
        limit (int): Maximum number of results to return
        
    Returns:
        list: List of business_ids for matching restaurants
    """
    if not cuisine:
        return []

    es_host = "https://search-resturants-hknviegcxlhrb3s7upbgusfffq.us-east-1.es.amazonaws.com/restaurant"
    username = "divyansh"
    password = "D!vyansh2201"
    url = f"{es_host}/_search"
    document = {   
        "size":5,
        "query":{
            "match":{
                "Cuisine":cuisine
            }
        }
    }
    response = requests.get(url, auth=(username, password), json=document)
    if response.status_code in [200, 201]:
        business_ids = [response.json()['hits']['hits'][i]['_source']['RestaurantID'] for i in range(limit)]
    
    return business_ids
    
def get_restaurant_details(business_ids):
    """
    Get detailed restaurant information from DynamoDB
    
    Args:
        business_ids (list): List of business IDs to fetch
        
    Returns:
        list: List of restaurant details
    """
    restaurants = []
    table = dynamodb.Table(DYNAMODB_TABLE)
    
    for business_id in business_ids:
        try:
            response = table.get_item(Key={'business_id': business_id})
            if 'Item' in response:
                restaurants.append(response['Item'])
        except Exception as e:
            logger.error(f"Error fetching restaurant {business_id} from DynamoDB: {str(e)}")
    
    return restaurants

def send_recommendation_email(email, restaurants, cuisine, dining_time, number_of_people):
    """
    Send email with restaurant recommendations
    
    Args:
        email (str): Recipient email address
        restaurants (list): List of restaurant details
        cuisine (str): Cuisine type requested
        dining_time (str): Requested dining time
        number_of_people (str): Number of people in the party
    """
    # Format restaurant information for email
    restaurant_list = ""
    for i, restaurant in enumerate(restaurants, 1):
        name = restaurant.get('name', 'Unknown Restaurant')
        address = restaurant.get('address', 'Address not available')
        rating = restaurant.get('rating', 'Not rated')
        review_count = restaurant.get('review_count', 'No reviews')
        
        restaurant_list += f"{i}. {name}\n"
        restaurant_list += f"   Address: {address}\n"
        restaurant_list += f"   Rating: {rating}/5\n"
        restaurant_list += f"   Number of Reviews: {review_count}\n\n"
    
    # Create email content
    subject = f"Your {cuisine} Restaurant Recommendations"
    
    body_text = f"""Hello,

Here are your restaurant recommendations for {cuisine} cuisine for {number_of_people} people at {dining_time}:

{restaurant_list}

Enjoy your meal!

Dining Concierge
"""
    
    body_html = f"""<html>
<head></head>
<body>
  <h2>Your Restaurant Recommendations</h2>
  <p>Here are your restaurant recommendations for <b>{cuisine}</b> cuisine for {number_of_people} people at {dining_time}:</p>
  
  <div style="margin-left: 20px;">
    {restaurant_list.replace('\n', '<br>')}
  </div>
  
  <p>Enjoy your meal!</p>
  <p>Dining Concierge</p>
</body>
</html>
"""
    
    try:
        response = ses.send_email(
            Source=SENDER_EMAIL,
            Destination={'ToAddresses': [email]},
            Message={
                'Subject': {'Data': subject},
                'Body': {
                    'Text': {'Data': body_text},
                    'Html': {'Data': body_html}
                }
            }
        )
        logger.info(f"Email sent! Message ID: {response['MessageId']}")
    except ClientError as e:
        logger.error(f"Error sending email: {e.response['Error']['Message']}")

def send_no_results_email(email, cuisine):
    """
    Send email when no restaurant recommendations are found
    
    Args:
        email (str): Recipient email address
        cuisine (str): Cuisine type requested
    """
    subject = "Restaurant Recommendations - No Results"
    
    body_text = f"""Hello,

We're sorry, but we couldn't find any {cuisine} restaurants matching your criteria.
Please try again with a different cuisine type or location.

Dining Concierge
"""
    
    body_html = f"""<html>
<head></head>
<body>
  <h2>No Restaurant Recommendations Found</h2>
  <p>We're sorry, but we couldn't find any <b>{cuisine}</b> restaurants matching your criteria.</p>
  <p>Please try again with a different cuisine type or location.</p>
  <p>Dining Concierge</p>
</body>
</html>
"""
    
    try:
        response = ses.send_email(
            Source=SENDER_EMAIL,
            Destination={'ToAddresses': [email]},
            Message={
                'Subject': {'Data': subject},
                'Body': {
                    'Text': {'Data': body_text},
                    'Html': {'Data': body_html}
                }
            }
        )
        logger.info(f"No results email sent! Message ID: {response['MessageId']}")
    except ClientError as e:
        logger.error(f"Error sending email: {e.response['Error']['Message']}")