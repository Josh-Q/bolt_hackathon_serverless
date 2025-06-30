# hackathon_serverless - DogeRace

A serverless Python + NodeJS application deployed on AWS Lambda to gamify AI model training with the use of trading signals and the blockchain.

---

## 📝 Description

This app performs allows users to and play and understand what forms of AI are better suited for tasks such as stock market pattern recognition using a Lambda function written in Python and NodeJS. It integrates with AWS services such as API Gateway, DynamoDB, Bedrock.

Frontend repository : [here](https://github.com/diniesganesan/bolt_hackathon)

---

## 🚀 Deployment Architecture

- **Bolt**--: Vibe coding for frontend 
- **Netlify**--: Frontend code deployment
- **AWS Lambda**: Core compute function
- **API Gateway** Handles REST calls + Lambda Authorizer 
- **DynamoDB**: Data store
- **CloudWatch**: Logs & monitoring
- **BedRock**: AI training and predictions
- **EventBridge**: Scheduling time based events 

> 📌 Hosted on AWS

---

## ⚙️ Tech Stack

- **Language**: Python 3.13 , Node.js 22.x
- **Deployment**: AWS Lambda

---


## Technical Architecture

<img width="832" alt="Screenshot 2025-06-28 at 1 27 44 PM" src="https://github.com/user-attachments/assets/c4602197-b149-4e90-83b2-bad6cc4391c5" />




## Lambda case uses

-- **Hackathon_2025_AI_Predication** 
Purpose: Interfaces with AWS Bedrock to get predictions from selected AI models.

-- **Hackathon_2025_Assessor_AI** 
Purpose: Central coordinator for each race round's AI analysis.

-- **Hackathon_2025_Authorizer** 
Purpose: Custom Lambda Authorizer for API Gateway to authenticated each request.

-- **Hackathon_2025_Bid** 
Purpose: Handles placing bids for races.

-- **Hackathon_2025_BlockChain_Common_Service** 
Purpose: Manages interactions with the Algorand blockchain.

-- **Hackathon_2025_Login** 
Purpose: Handles user login.

-- **Hackathon_2025_Sessions** 
Purpose: Manages race rounds information.

-- **Hackathon_2025_Users** 
Purpose: Manages user profiles.

-- **Hackathon_2025_Users_Bids** 
Purpose: Provides access to a user's historical or active bids.



