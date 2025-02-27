
import { LexRuntimeServiceClient, PostTextCommand } from '@aws-sdk/client-lex-runtime-service';

// Initialize Lex client
const lexRuntime = new LexRuntimeServiceClient({ region: 'us-east-1' });

function extractUserIdentifier(event) {
    if (event.requestContext?.identity?.sourceIp) {
        return `ip-${event.requestContext.identity.sourceIp.replace(/[.:]/g, '-')}`;
    }
    return 'web-user';
}

export const handler = async (event, context) => {
    try {
        console.log('Received event:', JSON.stringify(event, null, 2));
        
        // Parse the request body
        let requestBody;
        if (typeof event.body === 'string') {
            requestBody = JSON.parse(event.body);
        } else {
            requestBody = event;
        }
        
        console.log('Parsed request body:', JSON.stringify(requestBody, null, 2));
        
        // Extract message text
        if (!requestBody.messages || !requestBody.messages[0] || !requestBody.messages[0].unstructured) {
            throw new Error('Invalid request format');
        }
        
        const inputText = requestBody.messages[0].unstructured.text;
        
        // Get user ID for session management
        const userId = `user-${extractUserIdentifier(event)}`;
        console.log('Using userId:', userId);
        
        // Call Lex
        const postTextCommand = new PostTextCommand({
            botName: 'DiningConcierge',
            botAlias: 'DiningConcierge',
            userId: userId,
            inputText: inputText
        });
        
        const lexResponse = await lexRuntime.send(postTextCommand);
        console.log('Lex response:', JSON.stringify(lexResponse, null, 2));

        return {
          messages: [
              {
                  type: "unstructured", 
                  unstructured: {
                      text: lexResponse.message || "I'm still under development."
                  }
              }
          ]
      };
  } catch (error) {
      console.error('Error:', error);
      return {
          messages: [
              {
                  type: "unstructured",
                  unstructured: {
                      text: "Sorry, I encountered an error. Please try again."
                  }
              }
          ]
      };
  }
};
