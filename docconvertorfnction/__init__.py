import base64
import json
import logging
from datetime import datetime, timezone
import time
import uuid
import azure.functions as func
import fitz
import os
from PIL import Image
from pptx import Presentation
from azure.storage.blob import BlobServiceClient
from azure.storage.blob import (
    BlobServiceClient,
    BlobClient,
    BlobSasPermissions,
    generate_blob_sas
)
from datetime import datetime, timedelta
from azure.storage.queue import QueueClient
import io
import re
import csv



def main(myblob: func.InputStream) -> None:
    logging.info(f"Python blob trigger function processed blob \n"
                 f"Name: {myblob.name}\n"
                 f"Blob Size: {myblob.length} bytes")
    
    if(len(myblob.name.split('/')) == 4):
        filename=os.path.basename(myblob.name)
        filename_array = filename.split('.')
        #if array has more than 2 items then there are multiple dots in the filename
        item_count = len(filename_array)
        if(item_count > 2):
            file_type=filename_array[item_count-1].lower()
            file_name = ""
            for i in range(0, item_count-1):
                file_name += filename_array[i] + "."
            file_name = file_name[:-1]
        else:
            file_type=filename_array[1].lower()
            file_name=filename_array[0]
            
            
        logging.info("INFO: Starting the process for :" + filename)

        source_container_name=myblob.name.split('/')[0]
        target_language=myblob.name.split('/')[1]
        source_language=myblob.name.split('/')[2]


        #scanned, hybrid, original
        pdf_conversion=os.environ["pdf_conversion"]
        pdf_page_limit=os.environ["pdf_page_limit"]

        #scanned, original
        office_conversion="scanned"
        
        queue_name = os.environ["queue_name"]
        queue_client = QueueClient.from_connection_string(conn_str=os.environ["document_storage_connstr"], queue_name=queue_name)

        scannedpdf_output_storage = os.environ["document_storage_connstr"]
        converted_container = os.environ["converted_container"]     
        blob_service_client = BlobServiceClient.from_connection_string(scannedpdf_output_storage)
        container_client=blob_service_client.get_container_client(converted_container)

        mapping_file_container = os.environ["mapping_file_container"]
        mapping_container_client=blob_service_client.get_container_client(mapping_file_container)
        document_storage = os.environ["document_storage"]



        #don't allow file names with "--CustDocTranslator" in them
        if("--CustDocTranslator" in file_name):
            logging.error("ERROR: File name cannot contain --CustDocTranslator")
            raise Exception("ERROR: File name cannot contain --CustDocTranslator")
        
    
        if(file_type == "pdf"):
            #Open PDF file
            pdf_file = fitz.open("pdf", myblob.read())
            #Get the number of pages in PDF file
            page_nums = len(pdf_file)
            page_num=0
            num_only_text=0
            num_only_image=0
            num_text_image=0
            num_blank=0
            
            converted_file_name = ""
            
            if(pdf_conversion in[ "all", "scanned"]):
                logging.info("INFO: Processing PDF: Scanned Option")

                new_doc_textimages = fitz.open()
                file_part=1
                #Extract all images information from each page
                for page_num in range(page_nums):
                    page = pdf_file[page_num]
                    file_inprocess=True
                    logging.info("INFO: Page Num::::::-------------------------------------------"+ str(page_num+1))
                    if(len(page.get_text()) >0 and len(page.get_images())==0):
                        logging.info("INFO: Only text and no Images")
                        num_only_text +=1
                    elif(len(page.get_text()) ==0 and len(page.get_images())>0):
                        logging.info("INFO: Only Images and no Text")
                        logging.info("INFO: No of Images on the page:"+ str(len(page.get_images())))
                        num_only_image +=1
                    elif(len(page.get_text()) ==0 and len(page.get_images())==0):
                        logging.info("INFO: Blank Page")
                        num_blank +=1
                    elif(len(page.get_text()) >0 and len(page.get_images())>0):
                        logging.info("INFO: Text Plus Image")
                        logging.info("INFO: No of Images on the page:"+ str(len(page.get_images())))
                        num_text_image +=1
                    #create image of the page and add it to new doc
                    pix = page.get_pixmap(dpi=200)
                    opage = new_doc_textimages.new_page(width=page.rect.width, height=page.rect.height)
                    opage.insert_image(opage.rect, pixmap=pix)
                    if( ( (page_num+1) % int(pdf_page_limit)) ==0): 
                        pdf_bytes=new_doc_textimages.convert_to_pdf()
                        
                        if page_num+1 < page_nums:
                            converted_file_name = target_language +"/"+ source_language +"/"+file_name +"--CustDocTranslatorScannedPart-" + str(file_part).zfill(3) + ".pdf"                            
                            blob_client = container_client.get_blob_client(converted_file_name)
                        elif page_num+1 == page_nums:
                            converted_file_name = target_language +"/"+ source_language +"/"+file_name +"--CustDocTranslatorScannedPart-" + str(file_part).zfill(3) + "-Final.pdf"
                            blob_client = container_client.get_blob_client(converted_file_name)
                        try:    
                            blob_client.upload_blob(pdf_bytes, overwrite=True)
                        except Exception as e:
                            logging.error("ERROR: Exception while uploading blob: " + str(e))
                        
                        #add message to queuefortranslation
                        message_content = {
                            "source_language": source_language,
                            "target_language": target_language,
                            "file_name": converted_file_name,
                            "blob_url": blob_client.url
                        }
                        message = json.dumps(message_content)
                        try:
                            logging.info("INFO: Adding message to queue for: " + converted_file_name)
                            queue_client.send_message(message)
                            
                        except Exception as e:
                            logging.error("ERROR: Exception while adding message to queue: " + str(e))
                        
                        new_doc_textimages = fitz.open()
                        file_inprocess=False
                        file_part +=1
                
                if(file_inprocess==True):
                    pdf_bytes=new_doc_textimages.convert_to_pdf()
                    #following creates large file
                    # pdf_bytes=new_doc_textimages.tobytes()
                    converted_file_name = target_language +"/"+ source_language +"/"+file_name +"--CustDocTranslatorScannedPart-" + str(file_part).zfill(3) + "-Final.pdf"
                    blob_client = container_client.get_blob_client(converted_file_name)
                    try:
                        blob_client.upload_blob(pdf_bytes, overwrite=True)
                    except Exception as e:
                        logging.error("ERROR: Exception while uploading blob: " + str(e))
                    
                    #add message to queuefortranslation
                    message_content = {
                        "source_language": source_language,
                        "target_language": target_language,
                        "file_name": converted_file_name,
                        "blob_url": blob_client.url
                    }
                    message = json.dumps(message_content)
                    
                    try:
                        logging.info("INFO: Adding message to queue for: " + converted_file_name)
                        queue_client.send_message(message)
                    except Exception as e:
                        logging.error("ERROR: Exception while adding message to queue: " + str(e))
                
                new_doc_textimages.close()
                  
            if(pdf_conversion in[ "all", "hybrid"]):
                logging.info("INFO: Processing PDF: Hybrid Option")      
                new_doc_textonly = fitz.open()
                new_doc_textimages = fitz.open()
                page_num=0
                num_only_text=0
                num_only_image=0
                num_text_image=0
                num_blank=0                
                file_part=1
                page_mapping= []
                
                #Extract all images information from each page
                for page_num in range(page_nums):
                    page = pdf_file[page_num]
                    file_inprocess=True    
                    logging.info("INFO: Page Num::::::-------------------------------------------"+ str(page_num+1))
                    if(len(page.get_text()) >0 and len(page.get_images())==0):
                        logging.info("INFO: Only text and no Images")
                        num_only_text +=1
                        page_mapping.append("T")
                    elif(len(page.get_text()) ==0 and len(page.get_images())>0):
                        logging.info("INFO: Only Images and no Text")
                        logging.info("INFO: No of Images on the page:"+ str(len(page.get_images())))
                        num_only_image +=1 
                        page_mapping.append("I")
                    elif(len(page.get_text()) ==0 and len(page.get_images())==0):
                        logging.info("INFO: Blank Page")
                        num_blank +=1
                        page_mapping.append("T")
                    elif(len(page.get_text()) >0 and len(page.get_images())>0):
                        logging.info("INFO: Text Plus Image")
                        logging.info("INFO: No of Images on the page:"+ str(len(page.get_images())))
                        num_text_image +=1
                        page_mapping.append("I")
                total_I=num_only_image +num_text_image
                total_T=num_only_text +num_blank       

                logging.info("Num of Text Only Pages:::" + str(num_only_text))
                logging.info("Num of Image Only Pages:::" + str(num_only_image))
                logging.info("Num of Text and Image Pages:::" + str(num_text_image))
                logging.info("Num of Blank Pages:::" + str(num_blank))
                logging.info("mapping info: %s", page_mapping)
                # if all text(plus blank) or  all images(for sure scan doc)-- copy original
                if(total_T == page_nums ) or (num_only_image == page_nums ) :
                    logging.info("This file is Digital with all text or Scanned document. Copying the file as is to Converted")
                    file_extension = filename.split('.')[-1]
                    new_file_name = file_name +"--CustDocTranslatorSingleFile" + "." + file_extension
                    converted_file_name = target_language +"/"+ source_language +"/"+ new_file_name 
                    blob_client = container_client.get_blob_client(converted_file_name)
                    copy_file(scannedpdf_output_storage, source_container_name, converted_container,source_language, target_language, filename, new_file_name)
                    add_message(source_language,target_language, converted_file_name, blob_client.url, queue_client)
                # text + image -- Generate digital, scanned, originial and mapping files
                else:
                    logging.info("INFO: This file has Text and Images. Generating Digital and Scanned documents")
                    num_T=0
                    num_I=0
                    csv_file_path = target_language +"/"+ source_language +"/"+file_name + "--CustDocTranslatorMapping.csv"
                    mapping_data=[]
                    digital_pdf_name= target_language +"/"+ source_language +"/"+file_name +"--CustDocTranslatorMappedTextOnlyPages.pdf"
                    scan_pdf_name_substr= target_language +"/"+ source_language +"/"+file_name +"--CustDocTranslatorMappedScannedPart-"                            
                    digital_page_num=0
                    scan_page_num=0
                    num_scan_parts= (total_I+int(pdf_page_limit)-1)//int(pdf_page_limit)

                    for index, item in enumerate(page_mapping):
                        file_inprocess=True
                        if(item == "T"):
                           logging.info("INFO: Adding the page to digital PDF")
                           new_doc_textonly.insert_pdf(pdf_file, from_page = index, to_page = index)
                           num_T +=1
                           mapping_data.append([index+1, digital_pdf_name, num_T])
                        else:
                            logging.info("INFO: Adding the page to Scanned PDF")
                            num_I +=1
                            page = pdf_file[index]
                            pix = page.get_pixmap(dpi=200)
                            opage = new_doc_textimages.new_page(width=page.rect.width, height=page.rect.height)
                            opage.insert_image(opage.rect, pixmap=pix)
                            if(file_part <num_scan_parts): 
                                scan_page_num +=1
                                mapping_data.append([index+1, scan_pdf_name_substr + str(file_part).zfill(3) + ".pdf" , scan_page_num])
                            elif(file_part ==num_scan_parts):
                                scan_page_num +=1
                                mapping_data.append([index+1, scan_pdf_name_substr + str(file_part).zfill(3) + "-Final.pdf" , scan_page_num])
                            if ( ( num_I % int(pdf_page_limit)) ==0) :
                                pdf_ti_bytes=new_doc_textimages.convert_to_pdf()
                                if num_I < (num_only_image+num_text_image):
                                    converted_file_name = scan_pdf_name_substr + str(file_part).zfill(3) + ".pdf"                            
                                elif num_I == (num_only_image+num_text_image):
                                    converted_file_name = scan_pdf_name_substr + str(file_part).zfill(3) + "-Final.pdf"
                                blob_client = container_client.get_blob_client(converted_file_name)
                                try:
                                    blob_client.upload_blob(pdf_ti_bytes,overwrite=True)
                                except Exception as e:
                                    logging.error("ERROR: Exception while uploading blob: " + str(e))
                                    
                                add_message(source_language,target_language,converted_file_name,blob_client.url,queue_client)
                                new_doc_textimages = fitz.open()
                                file_inprocess=False
                                file_part +=1
                                scan_page_num=0
                                
                    if(new_doc_textimages.page_count >0 and file_inprocess==True):
                        pdf_ti_bytes=new_doc_textimages.convert_to_pdf()
                        converted_file_name = scan_pdf_name_substr + str(file_part).zfill(3) + "-Final.pdf"
                        blob_client = container_client.get_blob_client(converted_file_name)
                        try:
                            blob_client.upload_blob(pdf_ti_bytes,overwrite=True)
                        except Exception as e:
                            logging.error("ERROR: Exception while uploading blob: " + str(e))
                            
                        add_message(source_language,target_language,converted_file_name,blob_client.url,queue_client)
                    new_doc_textimages.close()

                    if(new_doc_textonly.page_count >0):
                        pdf_to_bytes=new_doc_textonly.tobytes(garbage=3, deflate=True)
                        blob_client = container_client.get_blob_client(digital_pdf_name)
                        try:
                            blob_client.upload_blob(pdf_to_bytes,overwrite=True)
                        except Exception as e:
                            logging.error("ERROR: Exception while uploading blob: " + str(e))
                            
                        add_message(source_language,target_language,digital_pdf_name,blob_client.url,queue_client)
                    new_doc_textonly.close() 
                    
                    
                    #copy the original file also
                    new_filename = re.sub(r'(?i)\.pdf$', '--CustDocTranslatorOriginal.pdf', filename)
                    copy_file(scannedpdf_output_storage, source_container_name, converted_container,source_language, target_language,filename, new_filename)
                    blob_url=document_storage+"/"+converted_container+"/"+ target_language +"/"+source_language +"/"+ new_filename
                    add_message(source_language,target_language,new_filename,blob_url,queue_client)
                    
                    #save the mapping CSV file
                    # Create an in-memory file-like object to store the CSV content
                    csv_buffer = io.StringIO()
                    # Write the data to the in-memory CSV file
                    csv_writer = csv.writer(csv_buffer)
                    csv_writer.writerows(mapping_data)
                    csv_buffer.seek(0)
                    # Upload the in-memory CSV to Azure Blob Storage
                    map_blob_client = mapping_container_client.get_blob_client(csv_file_path)
                    try:
                        map_blob_client.upload_blob(csv_buffer.read(), overwrite=True) 
                    except Exception as e:
                        logging.error("ERROR: Exception while uploading blob: " + str(e))



        elif(file_type in["html","xlsx","pptx","docx","ppt","doc","txt"]):
            logging.info("INFO: Processing -- " + file_type )
            #copy the original doc to output folder
            source_blob = blob_service_client.get_blob_client(source_container_name, target_language +"/"+ source_language + "/" + filename)
            
            file_extension = filename.split('.')[-1]
            converted_file_name = target_language +"/"+ source_language +"/"+file_name +"--CustDocTranslatorSingleFile" + "." + file_extension
            destination_blob = blob_service_client.get_blob_client(converted_container, converted_file_name)

            # Create a SAS token
            sas_token = generate_sas_token(blob_service_client=blob_service_client, source_blob=source_blob)
            source_blob_sas_url = source_blob.url + "?" + sas_token


            # Start the copy operation - specify False for the requires_sync parameter
            try:
                destination_blob.start_copy_from_url(source_url=source_blob_sas_url)
                
                while True:
                    blob_properties = destination_blob.get_blob_properties()
                    copy_status = blob_properties.copy.status
                    if copy_status != "pending":
                        break
                    time.sleep(1)

                if copy_status == "success":
                     logging.info(f'INFO: File {filename} copied successfully to container {converted_container} as {filename}')
                     #add message to queue
                     message_content = {
                        "source_language": source_language,
                        "target_language": target_language,
                        "file_name": converted_file_name,
                        "blob_url": destination_blob.url
                     }
                     message = json.dumps(message_content)
                     try:
                          logging.info("INFO: Adding message to queue for: " + converted_file_name)
                          queue_client.send_message(message)
                     except Exception as e:
                            logging.error("ERROR: Exception while adding message to queue: " + str(e))
                     
                     
                else:
                    logging.error(f"ERROR: Blob copy failed with status: {copy_status}.")
                   
            except Exception as e:
                logging.error(f"ERROR: An error occured when copying file: {e}")

        elif(file_type in[ "jpg", "bmp","png"]):
            logging.info("INFO: Processing image file")
            #img_file = fitz.open(file_path)
            img_file = fitz.open(file_type, myblob.read())
            new_pdf = fitz.open()
            for page in img_file:
                pix = page.get_pixmap(dpi=200)
                opage = new_pdf.new_page(width=page.rect.width, height=page.rect.height)
                opage.insert_image(opage.rect, pixmap=pix) 
            
            converted_file_name = target_language +"/"+ source_language +"/"+file_name +"--CustDocTranslatorImageFile.pdf"
            pdf_bytes=new_pdf.convert_to_pdf()
            blob_client = container_client.get_blob_client(converted_file_name)
            try:
                blob_client.upload_blob(pdf_bytes,overwrite=True)
            except Exception as e:
                logging.error("ERROR: Exception while uploading blob: " + str(e))
                
            new_pdf.close()
            
            
            #add message to queue
            message_content = {
                "source_language": source_language,
                "target_language": target_language,
                "file_name": converted_file_name,
                "blob_url": blob_client.url
            }
            message = json.dumps(message_content)
            
            try:
                logging.info("INFO: Adding message to queue for: " + converted_file_name)
                queue_client.send_message(message)
            except Exception as e:
                logging.error("ERROR: Exception while adding message to queue: " + str(e))
    else:
        logging.error("ERROR: File is uploaded to incorrect folder. It should be uploaded to Original/target language folder/source language folder")
        raise Exception("ERROR: File is uploaded to incorrect folder. It should be uploaded to Original/target language folder/source language folder")
    




def generate_sas_token( blob_service_client: BlobServiceClient, source_blob: BlobClient):


    # Create a SAS token that's valid for one hour, as an example
    sas_token = generate_blob_sas(
        account_name=blob_service_client.account_name,
        container_name=source_blob.container_name,
        blob_name=source_blob.blob_name,
        account_key=blob_service_client.credential.account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.now(timezone.utc) + timedelta(hours=1),
        start=datetime.now(timezone.utc) + timedelta(hours=-1)
    )

    return sas_token

def copy_file(document_storage_connstr, source_container, target_container,source_language, target_language, source_filename, target_filename):
    #copy the original doc to converted folder
    blob_service_client = BlobServiceClient.from_connection_string(document_storage_connstr)
    #filename = unquote(incoming_blob_name)
    source_blob = blob_service_client.get_blob_client(source_container, target_language +"/"+ source_language +"/"+source_filename)

    target_file_name=target_language +"/"+ source_language +"/"+target_filename
    destination_blob = blob_service_client.get_blob_client(target_container, target_file_name)
   
    # Create a SAS token
    sas_token = generate_sas_token(blob_service_client=blob_service_client, source_blob=source_blob)
    source_blob_sas_url = source_blob.url + "?" + sas_token
    # Start the copy operation - specify False for the requires_sync parameter    
    try:
        destination_blob.start_copy_from_url(source_url=source_blob_sas_url)        
        while True:
            blob_properties = destination_blob.get_blob_properties()
            copy_status = blob_properties.copy.status
            if copy_status != "pending":
                break
            time.sleep(1)

        if copy_status == "success":
                logging.info(f'INFO: File {source_filename} copied successfully to container {target_container} as {target_filename}')
        else:
            logging.error(f"ERROR: Blob copy failed with status: {copy_status}.")
            
    except Exception as e:
        logging.error(f"ERROR: An error occured when copying file: {e}")
 






def add_message(source_language,target_language,file_name,blob_url,queue_client):
    #add message to queue
    message_content = {
        "source_language": source_language,
        "target_language": target_language,
        "file_name": file_name,
        "blob_url": blob_url
    }
    message = json.dumps(message_content)
    try:
        logging.info("INFO: Adding message to queue for: " + file_name)
        queue_client.send_message(message)
        
    except Exception as e:
        logging.error("ERROR: Exception while adding message to queue: " + str(e))
                        

 







