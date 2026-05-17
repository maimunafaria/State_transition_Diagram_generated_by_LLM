---
source_type: dataset_example
case_id: case_03_online_marketplace
domain: Online Marketplace
complexity: complex
split_role: rag_train
---

# Online Marketplace — Polished Requirement Specification

## Requirement

Online Marketplace — Polished Requirement Specification

Functional Requirements
1. The system shall require the user to provide their details and create an account before they can join as a seller or customer.
2. The system shall allow the user to sign in and access their workspace after completing registration and verification.
3. The system shall enable the seller to add new products to the marketplace.
4. The system shall allow the seller to promote existing products on the platform.
5. The system shall enable the seller to communicate with customers through the platform.
6. The system shall allow the seller to leave the platform at any time, leading to logging out.
7. The system shall require the customer to sign in and access their personal dashboard upon joining.
8. The system shall allow the customer to explore products on the platform.
9. The system shall enable the customer to search and view available products during browsing.
10. The system shall allow the customer to either stop browsing or proceed with a purchase after viewing products.
11. The system shall add the selected product to the customer's cart and allow them to proceed to checkout if they decide to make a purchase.
12. The system shall handle payment during the checkout process.
13. The system shall allow the customer to communicate with a seller during their session.
14. The system shall enable the customer to report a seller if needed, based on previous interactions.
15. The system shall allow the customer to rate and review products after receiving them.
16. The system shall allow both the seller and the customer to log out by choosing to leave the platform at any time.

## Reference PlantUML

```plantuml
@startuml
title UML state machine diagram

state "Seller Registration" as SellerRegistration
SellerRegistration : entry/Unregistered Seller
SellerRegistration : do/Get Valid Seller Credentials
SellerRegistration : exit/Seller Account Registered

state "Seller Verification" as SellerVerification
SellerVerification : entry/Seller Account Registered
SellerVerification : do/Verify Seller
SellerVerification : exit/Login Seller

state "Seller Login" as SellerLogin
SellerLogin : entry/Unverified Seller
SellerLogin : entry/Seller not logged in
SellerLogin : do/Authenticate Seller
SellerLogin : exit/Logged In Successfully

state "Customer Login" as CustomerLogin
CustomerLogin : entry/Not Logged In
CustomerLogin : do/Authenticate Customer
CustomerLogin : exit/Successfully Logged In

state "Seller Home" as SellerHome
SellerHome : entry/Logged In Seller
SellerHome : do/Display Seller Dashboard
SellerHome : exit/Sale Products
SellerHome : exit/Promote Products
SellerHome : exit/Chat
SellerHome : exit/Logout

state "Customer Home" as CustomerHome
CustomerHome : entry/Customer Logged in
CustomerHome : do/Display Recommended/Promoted Products
CustomerHome : exit/View Product
CustomerHome : exit/Buy Product
CustomerHome : exit/Chat
CustomerHome : exit/Report Seller
CustomerHome : exit/Rate and Review

state "View Product" as ViewProduct
ViewProduct : entry/To View Products
ViewProduct : do/Search and View Products
ViewProduct : exit/Return to home
ViewProduct : exit/Buy Product

state "Buy Product" as BuyProduct
BuyProduct : entry/Opted to Buy
BuyProduct : do/Add product to cart
BuyProduct : exit/Proceed to Checkout

state "Make Purchase" as MakePurchase
MakePurchase : entry/Proceeded to Checkout
MakePurchase : do/Enable payment
MakePurchase : exit/Payment Successful
MakePurchase : exit/Payment Unsuccessful
MakePurchase : exit/Return to Home

state "Chat" as CustomerChat
CustomerChat : entry/To Chat
CustomerChat : do/Chat with Seller
CustomerChat : exit/Return to Home

state "Report Seller" as ReportSeller
ReportSeller : entry/To Report Seller
ReportSeller : entry/Seller in Purchase History
ReportSeller : do/Issue Report to Seller
ReportSeller : exit/Return to Home

state "Rate and Review" as RateReview
RateReview : entry/To Rate and Review
RateReview : entry/Product Delivered
RateReview : do/Rate and Review the product
RateReview : exit/Return to Home

state "Sale Products" as SaleProducts
SaleProducts : entry/To Sale Products
SaleProducts : do/Add new Product to Seller Inventory
SaleProducts : exit/Product added Successfully
SaleProducts : exit/Return to Home State

state "Promote Products" as PromoteProducts
PromoteProducts : entry/To Promote Products
PromoteProducts : entry/Product in Sale
PromoteProducts : do/Promote a Product
PromoteProducts : exit/Return to Home State

state "Chat" as SellerChat
SellerChat : entry/To Chat
SellerChat : entry/Seller Product in Sale
SellerChat : entry/Message from Customer
SellerChat : do/Enable chat with Customer
SellerChat : exit/Return to Home State

state "Logout" as Logout
Logout : entry/To Logout User
Logout : do/Logout User
Logout : exit/User Logged out

state J0 <<choice>>
state J1 <<choice>>
state J2 <<choice>>
state J3 <<choice>>
state J4 <<choice>>
state J5 <<choice>>
state J6 <<choice>>
state J7 <<choice>>
state J8 <<choice>>

[*] --> J0
J0 --> J1 : [Seller Portal]
J0 --> CustomerLogin : [Customer Portal]

J1 --> SellerRegistration : [New Seller]
J1 --> J2 : [Registered Seller]

SellerRegistration --> SellerVerification
SellerVerification --> J2
J2 --> SellerLogin

CustomerLogin --> J3
SellerLogin --> J7
J7 --> SellerHome : [Go To Home]

J3 --> CustomerHome : [Go To Home]

CustomerHome --> J4 : [Possible Activities]
J4 --> ViewProduct : [View Products]
J4 --> CustomerChat : [Chat]
J4 --> ReportSeller : [Report Seller]
J4 --> RateReview : [Rate and Review]
J4 --> J8 : [Logout]

ViewProduct --> J5
J5 --> J3 : [Not to Buy]
J5 --> BuyProduct : [Proceed to Buy]

BuyProduct --> MakePurchase
MakePurchase --> J3

CustomerChat --> J3
ReportSeller --> J3
RateReview --> J3

SellerHome --> J6 : [Possible Activities]
J6 --> PromoteProducts : [Promote Products]
J6 --> SellerChat : [Chat]
J6 --> SaleProducts
J6 --> J8 : [Logout]

SaleProducts --> J7

PromoteProducts --> J7
SellerChat --> J7

J8 -->  Logout
Logout --> [*]

@enduml

```
