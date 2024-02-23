# Translation Function App - Private (Isolated) Deployment

## 1&nbsp;&nbsp;Overview
### 1.1&nbsp;&nbsp;Purpose
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;The purpose of this guide is to provide detailed steps on how to deploy the supporting Azure components to support this solution.

### 1.2&nbsp;&nbsp;Scope
- Deploy a secured document translation solution using Azure Translator

### 1.3&nbsp;&nbsp;Prerequisites
- /27 Available Address Space
- Dedicated Subnet with a /27 Address Space

### 1.4&nbsp;&nbsp;Objects Deployed
- Virtual Network/Subnet (Optional:  Existing VNet can be used)
- Function App
- Function App Private Endpoint
- Function App Private Endpoint Network Interface Card
- Function App Private DNS Zone
- Storage Account
- Storage Account Private Endpoint – Blob
- Storage Account Private Endpoint Network Interface Card – Blob
- Storage Account Private DNS Zone – Blob
- Storage Account Private Endpoint – Queue
- Storage Account Private Endpoint Network Interface Card – Queue
- Storage Account Private DNS Zone – Queue
- Translation Service
- Translation Service Private Endpoint
- Translation Service Private Endpoint Network Interface Card
- Translation Service Private DNS Zone
- Network Security Group
- Management Workstation (Optional)

## 2&nbsp;&nbsp;Translator Service Deployment
### 2.1&nbsp;&nbsp;Resource Group  
#### 2.1.1&nbsp;&nbsp;Deployment
1.	Use the search box and enter **Resource groups** then select the object.
2.	At the **Resource group** blade click on **+ Create**.
3.	At the **Create a resource group** screen enter a descriptive name (Example: Translation-FunctionApp) then click on **Review + create**.
4.	Click **Create**.

### 2.2&nbsp;&nbsp;Translator Service
#### 2.2.1&nbsp;&nbsp;Deployment
1.	Use the search box and enter **Translators** then select the object.
2.	At the **Azure AI services | Translator** blade click on + **Create**.
3.	At the **Create Translator | Basics** screen enter the following then click on **Next**.

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Project Details*</ins>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Resource Group:**&nbsp;&nbsp;&nbsp;&nbsp;[Select Existing Resource Group]

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Instance Details*</ins>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Region:**&nbsp;&nbsp;&nbsp;&nbsp;[Select a Region]  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Name:**&nbsp;&nbsp;&nbsp;&nbsp;[Enter Translator Name]  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Pricing tier:**&nbsp;&nbsp;&nbsp;&nbsp;Standard S1 (Pay as you go)

4.	At the **Create Translator | Networking** screen click **Next**.
5.	At the **Create Translator | Identity** screen enter the following then click on **Review + create**:

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*System assigned managed identity*</ins>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Status:**&nbsp;&nbsp;&nbsp;&nbsp;On

6.	Click **Create**.

#### 2.2.2&nbsp;&nbsp;Retrieving Translator Key & Endpoint
1.	Once the resource deployment has completed click on **Go to resource**.
2.	At the **[Translator Name]** blade under **Resource Management** click on **Keys and Endpoint**.
3.	In the **Right-Pane** click on **Show keys** then click the **Copy button** to the right of **KEY 1** and store the **Translator Key value** which will be used later for the **Function App Configuration**.
4.	In the **Right-Pane** under **Web API** click the **Copy button** to the right of **Document Translation** and store the **Translator Endpoint URL value** which will be used later for the **Function App Configuration**.

## 3&nbsp;&nbsp;Function App Infrastructure Deployment
### 3.1&nbsp;&nbsp;Virtual Network
#### 3.1.1&nbsp;&nbsp;Deployment
1.	Use the search box and enter **Virtual Networks** then select the object.
2.	At the **Virtual Networks** blade click on **+ Create**.
3.	At the **Create virtual network | Basics** screen enter the following then click on **Nexts**.

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Project Details*</ins>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Resource Group:**&nbsp;&nbsp;&nbsp;&nbsp;[Select Previously Created Resource Group]  

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Instance Details*</ins>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Region:**&nbsp;&nbsp;&nbsp;&nbsp;[Select a Region]  

4.  At the **Create virtual network | Security** click **Next**.
5.	At the **CCreate virtual network | IP Addresses** screen create/enter the following then click on **Review + create**.

*Example IPv4 address space:*  
172.16.2.0/26

*Example Subnets:*  
| **Subnet Name**   | **Subnet address space** |
| :---------------- | :----------------------  |
| ServerFarm        | 172.16.2.0/27            |
| Infrastructure    | 172.16.2.32/28           |
| PrivateEndpoints  | 172.16.2.48/28           |

6.	Click **Create**.

### 3.2&nbsp;&nbsp;Translator  
#### 3.2.1&nbsp;&nbsp;Create Translator Private Endpoint
1.	In the **Azure Portal** search box enter the name of the previously created **Translator** then once it is found click on it.
2.	At the **[Translator Name]** blade under **Resource Management** click on **Networking**.
3.	In the **Right-Pane** click on **Private endpoint connections** then click on **+ Private endpoint**.
4.	At the **Create private endpoint | Basics** screen enter/select the following then click **Next | Resource:**

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Project Details*</ins>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Subscription:**&nbsp;&nbsp;&nbsp;&nbsp;[Select Storage Account Subscription]  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Resource Group:**&nbsp;&nbsp;&nbsp;&nbsp;[Select Previously Created Resource Group]  

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Instance details*</ins>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Name:**&nbsp;&nbsp;&nbsp;&nbsp;[Enter a descriptive name]  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;*Example:  Functionapptranslator-account*  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Name:**&nbsp;&nbsp;&nbsp;&nbsp;[Enter a descriptive name]  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Region:**&nbsp;&nbsp;&nbsp;&nbsp;[Select a Region]  

5.	At the **Create private endpoint | Resource** screen enter/select the following then click **Next : Virtual Network:**  

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Target sub-resource:**&nbsp;&nbsp;&nbsp;&nbsp;[Use the pulldown to select account]  

6.	At the **Create private endpoint | Virtual Network** screen enter/select the following then click **Next : Virtual Tags:**

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Networking*</ins>  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Virtual network:**&nbsp;&nbsp;&nbsp;&nbsp;[Select Previously Created Virtual Network]  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Subnet:**&nbsp;&nbsp;&nbsp;&nbsp;[Select PrivateEndpoints Subnet]  

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Private IP configuration:**&nbsp;&nbsp;&nbsp;&nbsp;Dynamically allocated IP address

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Private DNS integration*</ins>  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Integrate with private dns zone:**&nbsp;&nbsp;&nbsp;&nbsp;Yes  

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;*Make sure for each DNS Zone that the Subscription and Resource Group are selected where the Function App Infrastructure exists*

7.	At the **Create a private endpoint | Tags** screen click **Next : Review + create**.
8.	At the **Create a private endpoint | Review + create** screen click **Create**.

### 3.2&nbsp;&nbsp;Storage Accounts
#### 3.2.1&nbsp;&nbsp;Function App Job Storage Deployment  
1.	Use the search box and enter **Storage accounts** then select the object.
2.	At the **Storage accounts** blade click on **+ Create**.
3.	At the **Create a storage account | Basics** screen enter the following then click on Review.

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Project Details*</ins>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Resource Group:**&nbsp;&nbsp;&nbsp;&nbsp;[Select Previously Created Resource Group]  

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Instance Details*</ins>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Storage account name:**&nbsp;&nbsp;&nbsp;&nbsp;[Enter a Storage Account Name]  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Region:**&nbsp;&nbsp;&nbsp;&nbsp;[Select a Region]  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Performance:**&nbsp;&nbsp;&nbsp;&nbsp;Standard  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Redundancy::**&nbsp;&nbsp;&nbsp;&nbsp;Geo-redundant storage (GRS)

4.	Click **Create**.

#### 3.2.2&nbsp;&nbsp;Create Storage Account Containers  
1.	At the Your deployment is complete screen click on **Go to resource**.
2.	At the **[Storage Account Name]** blade under **Data storage** click on **Containers**.
3.	In the **Right-Pane** click on **+ Container**.
4.	At the **New container** pop-out blade enter the following then click **Create:**

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Name::**&nbsp;&nbsp;&nbsp;&nbsp;input-simple

5.	In the Right-Pane click on + Container.
6.	At the New container pop-out blade enter the following then click Create:

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Name::**&nbsp;&nbsp;&nbsp;&nbsp;output-simple

#### 3.2.3&nbsp;&nbsp;Create Storage Account Blob Private Endpoint  
1.	At the **[Storage Account Name]** blade under **Settings + networking** click on **Networking**.
2.	In the **Right-Pane** click on **Private endpoint connections** then click on **+ Private endpoint**.
3.	At the **Create private endpoint | Basics** screen enter/select the following then click **Next | Resource:**

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Project Details*</ins>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Subscription:**&nbsp;&nbsp;&nbsp;&nbsp;[Select Storage Account Subscription]  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Resource Group:**&nbsp;&nbsp;&nbsp;&nbsp;[Select Previously Created Resource Group]  

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Instance Details*</ins>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Name:**&nbsp;&nbsp;&nbsp;&nbsp;Enter a descriptive name  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Region:**&nbsp;&nbsp;&nbsp;&nbsp;[Select a Region]  

5.	At the Create private endpoint | Resource screen enter/select the following then click Next : Virtual Network:

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Target sub-resource:**&nbsp;&nbsp;&nbsp;&nbsp;[Use the pulldown to select blob]

6.	At the Create private endpoint | Virtual Network screen enter/select the following then click Next : Virtual Tags:

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Networking*</ins>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Virtual network:**&nbsp;&nbsp;&nbsp;&nbsp;[Select Previously Created Virtual Network]  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Subnet:**&nbsp;&nbsp;&nbsp;&nbsp;[Select PrivateEndpoints Subnet]  

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Private IP configuration:**&nbsp;&nbsp;&nbsp;&nbsp;Dynamically allocated IP address		

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Private DNS integration*</ins>  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Subnet:**&nbsp;&nbsp;&nbsp;&nbsp;Yes  

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Make sure for each DNS Zone that the Subscription and Resource Group are selected where the Function App Infrastructure exists

7.	At the Create a private endpoint | Tags screen click Next : Review + create.
8.	At the Create a private endpoint | Review + create screen click Create.

#### 3.2.4&nbsp;&nbsp;Create Storage Account Queue Private Endpoint  
1.	In the Azure Portal search box enter the name of the previously created Storage Account then once it is found click on it.
2.	At the [Storage Account Name] blade under Settings + networking click on Networking.
3.	In the Right-Pane click on Private endpoint connections then click on + Private endpoint.
4.	At the Create private endpoint | Basics screen enter/select the following then click Next | Resource:

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Project Details*</ins>  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Subscription:**&nbsp;&nbsp;&nbsp;&nbsp;[Select Storage Account Subscription]  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Resource Group:**&nbsp;&nbsp;&nbsp;&nbsp;[Select Previously Created Resource Group]  

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Instance Details*</ins>  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Name:**&nbsp;&nbsp;&nbsp;&nbsp;Enter a descriptive name  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Region:**&nbsp;&nbsp;&nbsp;&nbsp;[Select a Region]  

5.	At the Create private endpoint | Resource screen enter/select the following then click Next : Virtual Network:

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Target sub-resource:**&nbsp;&nbsp;&nbsp;&nbsp;[Use the pulldown to select blob]

6.	At the Create private endpoint | Virtual Network screen enter/select the following then click Next : Virtual Tags:

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Networking*</ins>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Virtual network:**&nbsp;&nbsp;&nbsp;&nbsp;[Select Previously Created Virtual Network]  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Subnet:**&nbsp;&nbsp;&nbsp;&nbsp;[Select PrivateEndpoints Subnet]  

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Private IP configuration:**&nbsp;&nbsp;&nbsp;&nbsp;Dynamically allocated IP address		

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Private DNS integration*</ins>  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Subnet:**&nbsp;&nbsp;&nbsp;&nbsp;Yes  

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Make sure for each DNS Zone that the Subscription and Resource Group are selected where the Function App Infrastructure exists

7.	At the Create a private endpoint | Tags screen click Next : Review + create.
8.	At the Create a private endpoint | Review + create screen click Create.

#### 3.2.5&nbsp;&nbsp;Assign Translator System Managed Identity Storage Permissions  
1.	In the Azure Portal search box enter the name of the previously created Storage Account then once it is found click on it.
2.	At the [Storage Account Name] blade click on Access Control (IAM).
3.	In the Right-Pane click on + Add | Add role assignment.
4.	At the Add role assignment | Role blade under Job function roles type Storage Blob Data Contributor and click on it when found then click Next.
5.	At the Add role assignment | Members blade select Managed identity then click on + Select Members.
6.	At the Select managed identities pop-out window use the Managed identity pull-down menu to select Translator.
7.	Click the previously created Translator then click Select.
8.	Click Review + assign.

#### 3.2.6&nbsp;&nbsp;Retrieving Storage Account Connection String  
9.	Use the search box and enter Storage accounts then select the object.
10.	At the Storage accounts blade locate and click on the previously created Storage Account.
11.	At the [Storage Account Name] blade under Security + networking click on Access keys.
12.	In the Right-Pane under key1 for the Connection string value click Show then click the Copy button and store the Storage Account 

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Connection string value which will be used later for the Function App Configuration.

#### 3.2.7&nbsp;&nbsp;Retrieving Storage Account Blob Endpoint  
1.	Use the search box and enter Storage accounts then select the object.
2.	At the Storage accounts blade locate and click on the previously created Storage Account.
3.	At the [Storage Account Name] blade under Settings click on Endpoints.
4.	In the Right-Pane under Blob service locate the Primary endpoint blob service URL then click the Copy button and store the Storage Account Blob Endpoint URL value which will be used later for the Function App Configuration.

## 4&nbsp;&nbsp;Function App Deployment
### 4.1&nbsp;&nbsp;Function App
#### 4.1.1&nbsp;&nbsp;Deployment
1.	Use the search box and enter Function App then select the object.
2.	At the Function App blade click on + Add.
3.	At the Create Function App | Basics screen enter the following then click on Next : Hosting.

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Project Details*</ins>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Resource Group:**&nbsp;&nbsp;&nbsp;&nbsp;[Select Previously Created Resource Group]  

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Instance Details*</ins>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Function App name:**&nbsp;&nbsp;&nbsp;&nbsp;[Enter Function App Name]  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Runtime stack:**&nbsp;&nbsp;&nbsp;&nbsp;Python  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Version:**&nbsp;&nbsp;&nbsp;&nbsp;3.10  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Region:**&nbsp;&nbsp;&nbsp;&nbsp;[Select a Region]  

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Hosting*</ins>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Hosting options and plans:**&nbsp;&nbsp;&nbsp;&nbsp;App service plan  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Linux Plan (USGov Virginia):**&nbsp;&nbsp;&nbsp;&nbsp;Follow below Steps to select existing  	 
1.	Click on Create new.
2.	At the New App Service Plan enter a descriptive name for the Name then click OK. (Example:  Translator-FunctionApp)

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Pricing plan:**&nbsp;&nbsp;&nbsp;&nbsp;Premium V3 PxV3			

4.	At the Create Function App | Storage screen enter the following then click on Next : Networking.

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Storage*</ins>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Storage type:**&nbsp;&nbsp;&nbsp;&nbsp;Azure Storage  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Storage account:**&nbsp;&nbsp;&nbsp;&nbsp;[Select previously created Function App Storage Account]  

5.	At the Create Function App | Networking screen enter the following then click on Next : Monitoring.

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Enable public access:**&nbsp;&nbsp;&nbsp;&nbsp;On  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Enable network injection:**&nbsp;&nbsp;&nbsp;&nbsp; Off

6.	At the Create Logic App | Monitoring screen enter the following then click on Review + create.

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Application Insights*</ins>  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Enable Application Insights:**&nbsp;&nbsp;&nbsp;&nbsp;No

7.	Click Create.

#### 4.1.2&nbsp;&nbsp;Create Function App Private Endpoint  
1.	In the Azure Portal search box enter the name of the previously created Function App then once it is found click on it.
2.	At the [Function App Name] blade under Settings click on Networking.
3.	In the Right-Pane under Inbound Traffic click on Private endpoints.
4.	At the Private Endpoint connections blade click + Add | Advanced.
5.	At the Create private endpoint | Basics screen enter/select the following then click Next | Resource:

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Project Details*</ins>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Subscription:**&nbsp;&nbsp;&nbsp;&nbsp;[Select Storage Account Subscription]  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Resource Group:**&nbsp;&nbsp;&nbsp;&nbsp;[Select Previously Created Resource Group]  

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Instance Details*</ins>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Name:**&nbsp;&nbsp;&nbsp;&nbsp;[Enter a descriptive name]  (Example: Translatorfucntionapp-sites)  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Runtime stack:**&nbsp;&nbsp;&nbsp;&nbsp;Python  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Region:**&nbsp;&nbsp;&nbsp;&nbsp;[Select a Region]  

6.	At the Create private endpoint | Resource screen enter/select the following then click Next : Virtual Network:

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Target sub-resource:**&nbsp;&nbsp;&nbsp;&nbsp;[Use the pulldown to select sites]  

7.	At the Create private endpoint | Virtual Network screen enter/select the following then click Next : Virtual Tags:

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Networking*</ins>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Virtual network:**&nbsp;&nbsp;&nbsp;&nbsp;[Select Previously Created Virtual Network]  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Subnet:**&nbsp;&nbsp;&nbsp;&nbsp;[Select PrivateEndpoints Subnet]  

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Private IP configuration:**&nbsp;&nbsp;&nbsp;&nbsp;Dynamically allocated IP address  		

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Private DNS integration*</ins>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Integrate with private dns zone:**&nbsp;&nbsp;&nbsp;&nbsp;Yes

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Make sure for each DNS Zone that the Subscription and Resource Group are selected where the Function App Infrastructure exists

8.	At the Create a private endpoint | Tags screen click Next : Review + create.
9.	At the Create a private endpoint | Review + create screen click Create.

#### 4.1.3&nbsp;&nbsp;Add Function App Virtual Network Integration  
1.	In the Azure Portal search box enter the name of the previously created Function App then once it is found click on it.
2.	At the [Function App Name] blade under Settings click on Networking.
3.	In the Right-Pane under Outbound Traffic click on VNet intergration.
4.	At the VNet Integration blade click + Add VNet.
5.	At the Add VNet Integration pop-out blade use the Virtual Network pull-down menu to select the Function App Virtual Network.
6.	Use the Subnet pull-down menu to select the ServerFarm Subnet then click OK.

#### 4.1.4&nbsp;&nbsp;Function App Configuration  
1.	In the Azure Portal search box enter the name of the previously created Function App then once it is found click on it.
2.	At the [Function App Name] blade under Settings click on Configuration.
3.	In the Right-Pane under Application settings click on + New application setting.
4.	At the Add/Edit application setting enter the following then click OK:

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Name:**&nbsp;&nbsp;&nbsp;&nbsp;document_storage_connstr  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Value:**&nbsp;&nbsp;&nbsp;&nbsp;[Enter the Storage Account Connection String without brackets]

5.	In the Right-Pane under Application settings click on + New application setting.
6.	At the Add/Edit application setting enter the following then click OK:

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Name:**&nbsp;&nbsp;&nbsp;&nbsp;target_blob_url  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Value:**&nbsp;&nbsp;&nbsp;&nbsp;[Enter the Storage Account Blob Endpoint URL without brackets with “output-simple” added to the URL ]

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Example:**&nbsp;&nbsp;&nbsp;&nbsp;https://[storageaccountname].blob.core.usgovcloudapi.net/output-simple

7.	At the Add/Edit application setting enter the following then click OK:

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Name:**&nbsp;&nbsp;&nbsp;&nbsp;translator_endpoint  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Value:**&nbsp;&nbsp;&nbsp;&nbsp;[Enter the Translator Endpoint URL without brackets]

8.	In the Right-Pane under Application settings click on + New application setting.
9.	At the Add/Edit application setting enter the following then click OK:

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Name:**&nbsp;&nbsp;&nbsp;&nbsp;translator_KEY  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Value:**&nbsp;&nbsp;&nbsp;&nbsp;[Enter the Translator Endpoint URL without brackets]

10.	At the top of the Right-Pane click on General settings.
11.	Under Stack settings | Basic Auth Publishing Credentials click On.
12.	At the top of the Right-Pane click Save then Continue.

## 5&nbsp;&nbsp;Deploy Function  
#### 5.1.1&nbsp;&nbsp;[Add Function upload process here]


## 6&nbsp;&nbsp;Management Network Isolation  
### 6.1&nbsp;&nbsp;Management Azure Virtual Machine  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;To manage the Function App which will have Public Access disabled a Management workstation will be needed.  This workstation must be able to route to the Function App over Private Endpoints.  To do this, a Virtual Network Peering must be set up between the FunctionApp-VNet and the Virtual Network where the Management Workstation exists.  

#### 6.1.1&nbsp;&nbsp;Virtual Network Peering (Only needed if creating new VNet)  
1.	Use the search box and enter Virtual Networks then select the object.
2.	At the Virtual networks blade click on the Function App VNet.
3.	In the Left-Pane scroll down to the Settings section and click on Peerings.
4.	In the Right-Pane click on a + Add.
5.	At the Add peering screen under This virtual network enter and select the following:

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Peering link name:**&nbsp;&nbsp;&nbsp;&nbsp;[Enter VNet Name of Management Workstation]

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Select:**  
- Allow access to remote virtual 
- Allow traffic to remote virtual network

6.	At the Add peering screen under Remote virtual network enter and select the following then click Add:

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Peering link name:**&nbsp;&nbsp;&nbsp;&nbsp;FunctionApp-VNet		

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[Use the Virtual network pull-down menu to select the Virtual Network containing the Management Workstation]

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Select:**  
- Allow access to remote virtual 
- Allow traffic to remote virtual network

### 6.2&nbsp;&nbsp;Network Security Group  
#### 6.2.1&nbsp;&nbsp;Deployment  
1.	Use the search box and enter Network Security Groups then select the object.
2.	At the Network security groups blade click on + Create.
3.	At the Create network security group | Basics screen enter the following then click on Next : IP Addresses.

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Project Details*</ins>  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Resource Group:**&nbsp;&nbsp;&nbsp;&nbsp;[Select Previously Created Resource Group]  

#### &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<ins>*Instance Details*</ins>  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Name:**&nbsp;&nbsp;&nbsp;&nbsp;Enter a descriptive name  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**Region:**&nbsp;&nbsp;&nbsp;&nbsp;[Select a Region]  

4.	Click on Create.

#### 6.2.2&nbsp;&nbsp;Create Deny All Rules  
1.	At the Your deployment is complete screen click on Go to resource.
2.	At the [Network Security Group Name] blade under Settings click on Inbound security rules.
3.	At the [Network Security Group Name] | Inbound security rules blade click on + Add.
4.	At the Add inbound security rules pop-out windows enter the following then click Add:

| **Property**             | **Value**        |
| :----------------------- | :--------------- |
| Source:                  | Any              |
| Source port ranges:      | *                |
| Destination:             | Any              |
| Service:                 | Custom           |
| Destination port ranges: | *                |
| Protocol:                | Any              |
| Action:                  | Deny             |
| Priority:                | 4000             |
| Name:                    | Deny-All-Inbound |

5.	On the Left-Pane under Settings click on Outbound security rules.
6.	At the [Network Security Group Name] | Outbound security rules blade click on + Add.
7.	At the Add outbound security rules pop-out windows enter the following then click Add:

| **Property**             | **Value**         |
| :----------------------- | :---------------- |
| Source:                  | Any               |
| Source port ranges:      | *                 |
| Destination:             | Any               |
| Service:                 | Custom            |
| Destination port ranges: | *                 |
| Protocol:                | Any               |
| Action:                  | Deny              |
| Priority:                | 4000              |
| Name:                    | Deny-All-Outbound |
 
 #### 6.2.3&nbsp;&nbsp;Create Allow All Virtual Network Rules  
1.	At the [Network Security Group Name] | Inbound security rules blade click on + Add.
2.	At the Add inbound security rules pop-out windows enter the following then click Add:


| **Property**             | **Value**                        |
| :----------------------- | :------------------------------- |
| Source:                  | Service Tag                      |
| Source service tag:      | Virtual Network                  |
| Source port ranges:      | **                               |
| Destination:             |  Service Tag                     |
| Destination service tag: | Virtual Network                  |
| Service:                 | Custom                           |
| Destination port ranges: | *                                |
| Protocol:                | Any                              |
| Action:                  | Allow                            |
| Priority:                | 3500                             |
| Name:                    | Allow-All-Inbound-VirtualNetwork |

3.	On the Left-Pane under Settings click on Outbound security rules.
4.	At the [Network Security Group Name] | Outbound security rules blade click on + Add.
5.	At the Add outbound security rules pop-out windows enter the following then click Add:

| **Property**             | **Value**                         |
| :----------------------- | :-------------------------------- |
| Source:                  | Service Tag                       |
| Source service tag:      | Virtual Network                   |
| Source port ranges:      | **                                |
| Destination:             |  Service Tag                      |
| Destination service tag: | Virtual Network                   |
| Service:                 | Custom                            |
| Destination port ranges: | *                                 |
| Protocol:                | Any                               |
| Action:                  | Allow                             |
| Priority:                | 3500                              |
| Name:                    | Allow-All-Outbound-VirtualNetwork |

#### 6.2.4&nbsp;&nbsp;Associate NSG to Subnets  
1.	At the [Network Security Group Name] blade under Settings click on Subnets.
2.	In the Right-Pane click on + Associate.
3.	At the Associate subnet pop-out windows use the Virtual network pull-down menu to select the previously created Virtual Network and use the Subnet pull-down menu to select the ServerFarm subnet.
4.	Repeat the previous step for the other 2 Subnets listed below:
- PrivateEndpoints
- Infrastructure

#### 6.2.5&nbsp;&nbsp;Storage Account  
1.	In the Azure Portal search box enter the name of the previously created Storage Account then once it is found click on it.
2.	At the [Storage Account Name] blade under Security + Networking click on Networking.
3.	Under Firewalls and virtual networks click on Disabled then click Save.

#### 6.2.6&nbsp;&nbsp;Translator  
1.	In the Azure Portal search box enter the name of the previously created Translators then once it is found click on it.
2.	At the [Translator Name] blade under Resource Management click on Networking.
3.	Under Firewalls and virtual networks click on Disabled then click Save.

#### 6.2.6&nbsp;&nbsp;Function App  
1.	In the Azure Portal search box enter the name of the previously created Function App then once it is found click on it.
2.	At the [Translator Name] blade under Settings click on Networking.
3.	In the Right-Pane under Inbound Traffic click on Access restriction.
4.	At the Access Restrictions screen under App access uncheck Allow public access and click Save then Continue.