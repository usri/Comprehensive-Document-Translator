import io
import json
from urllib.parse import unquote, urlparse
import azure.functions as func
import logging
from azure.storage.blob import BlobServiceClient
from azure.storage.blob import (
    BlobServiceClient,
    BlobClient,
    BlobLeaseClient,
    BlobSasPermissions,
    generate_blob_sas
)
from datetime import datetime, timedelta, timezone
import os
import re
import fitz
import time
import requests, uuid
import csv



is_image_file = False
is_single_file = False
is_multi_part_file = False
is_mapping_file = False
is_original_file = False

mapping_file_container = os.environ["mapping_file_container"]
document_storage = os.environ["document_storage"]
document_storage_connstr = os.environ["document_storage_connstr"]
converted_container = os.environ["converted_container"]
translated_container = os.environ["translated_container"]
final_container = os.environ["final_container"]

def main(msg: func.QueueMessage):
    
    global is_image_file
    global is_single_file
    global is_multi_part_file
    global is_mapping_file
    global is_original_file
    global mapping_file_container
    global document_storage
    global document_storage_connstr
    global converted_container
    global translated_container
    global final_container
    
    
    logging.info('Python queue trigger function processed a queue item: %s',
                 msg.get_body().decode('utf-8'))
    
   
    
    
    result = json.dumps({
        'id': msg.id,
        'body': msg.get_body().decode('utf-8'),
        'expiration_time': (msg.expiration_time.isoformat()
                            if msg.expiration_time else None),
        'insertion_time': (msg.insertion_time.isoformat()
                           if msg.insertion_time else None),
        'time_next_visible': (msg.time_next_visible.isoformat()
                              if msg.time_next_visible else None),
        'pop_receipt': msg.pop_receipt,
        'dequeue_count': msg.dequeue_count
    })
    
    decoded_msg = json.loads(result)
    source_blob_url = decoded_msg['body']
    translated_blob_name = source_blob_url.replace("/converted/", "/translated/")
    translated_blob_name = translated_blob_name.replace(document_storage, "")
    
    logging.info(f"INFO: Aggregator triggered for blob {translated_blob_name}")
    
    
    if "--CustDocTranslatorImageFile.pdf" in source_blob_url:
        is_image_file = True
    else:
        is_image_file = False
        
    if "--CustDocTranslatorSingleFile" in source_blob_url:
        is_single_file = True
    else:
        is_single_file = False

    if "--CustDocTranslatorScannedPart-" in source_blob_url:
        is_multi_part_file = True
    else:
        is_multi_part_file = False
        
    if "--CustDocTranslatorMapping.csv" in source_blob_url:
        is_mapping_file = True
    else:
        is_mapping_file = False
        
    if "--CustDocTranslatorOriginal.pdf" in source_blob_url:
        is_original_file = True
    else:
        is_original_file = False
    
    
    # Check if all parts are complete: Start to Final
    if (is_multi_part_file):
        try:
            merge_pdfs_in_blob_storage(document_storage_connstr, final_container, translated_container, translated_blob_name)
            logging.info("INFO: PDF merge completed successfully.")
        except Exception as e:
            logging.error(f"ERROR: PDF merge failed. {e}")
        finally:
            try:
                clean_up_working_files(document_storage_connstr, converted_container, translated_container, translated_blob_name)
                logging.info("INFO: PDF merge and clean up successfully completed.")
            except Exception as e:
                logging.error(f"ERROR: Error during clean up. {e}")
            
    elif(is_mapping_file):
        try:
            map_files_to_final(document_storage_connstr, final_container, translated_container, source_blob_url)
        except Exception as e:
            logging.error(f"ERROR: AggregatorFunction - Mapped document was not copied to Final container. Source Blob: {source_blob_url} ERRMSG: {e}")
        finally:
            try:
                clean_up_working_files(document_storage_connstr, converted_container, translated_container, translated_blob_name)
                logging.info("INFO: Copy and clean up successfully completed.")
            except Exception as e:
                logging.error(f"ERROR: Error during clean up. {e}")
                
    elif(is_image_file or is_single_file or is_original_file):
        logging.info("INFO: Source file is image file. Copying the translated file to Final folder")
        try:
            copy_file_to_final(document_storage_connstr, final_container, translated_container, translated_blob_name)
            logging.info("INFO: copied the file to final folder successfully.")
        except Exception as e:
            logging.error(f"ERROR: copy to final folder failed. {e}")
        #cleanup might not work. This needs to be updated
        finally:
            try:
                clean_up_working_files(document_storage_connstr, converted_container, translated_container, translated_blob_name)
                logging.info("INFO: Copy and clean up successfully completed.")
            except Exception as e:
                logging.error(f"ERROR: Error during clean up. {e}")


   
def map_files_to_final(document_storage_connstr, final_container, translated_container, mapping_file_blob):
    global mapping_file_container
    target_pdf = fitz.open()
    file_map_array = []
    
    #get the filename from the mapping file url  uk/en/testfile--CustDocTranslatorMapping.csv
    try:
        parsed_url = urlparse(mapping_file_blob)
        path_parts = parsed_url.path.lstrip('/').split('/')
        mapping_file_name = '/'.join(path_parts[1:])
        prefix = get_document_prefix(mapping_file_name, translated_container)
        
        blob_service_client = BlobServiceClient.from_connection_string(document_storage_connstr)
        mapping_container_client = blob_service_client.get_container_client(mapping_file_container)
        
        map_data = io.BytesIO()
        try:
            blob_data = mapping_container_client.download_blob(mapping_file_name)
            blob_data.readinto(map_data)
            map_data.seek(0)
            csv_reader = csv.reader(io.StringIO(map_data.getvalue().decode('utf-8')))
            file_map_array = [row for row in csv_reader]
        except Exception as e:
            logging.error(f"ERROR: map_files_to_final - Error downloading mapping file. File: {mapping_file_name} {e}")
            
        
    
    except Exception as e:
        logging.error(f"ERROR: Error during mapping. {e}")
    
    previous_pdf_name = ""
    source_pdf = None
    
    for file_map in file_map_array:
        if len(file_map) == 3:
            source_pdf_name = file_map[1]
            source_page_number = file_map[2]
            translated_container_client = blob_service_client.get_container_client(translated_container)
            translated_blob_client = translated_container_client.get_blob_client(source_pdf_name)
            try:
                #download the source pdf if it is not already downloaded
                if previous_pdf_name != source_pdf_name:
                    if source_pdf:
                        source_pdf.close()
                    blob_data = translated_blob_client.download_blob().readall()
                    blob_stream = io.BytesIO(blob_data)
                    source_pdf = fitz.open(stream=blob_stream.getvalue(), filetype='pdf')
                    previous_pdf_name = source_pdf_name
                    
                target_pdf.insert_pdf(source_pdf, from_page=int(source_page_number) - 1, to_page=int(source_page_number) - 1)
                
            except Exception as e:
                logging.error(f"ERROR: map_files_to_final - Error downloading source pdf blob. SourcePDF: {source_pdf_name}  ERRMSG: {e}")
                

    # Close the last opened source pdf
    if source_pdf:
        source_pdf.close()
            
    # Write the merged PDF to a BytesIO object
    output_stream = io.BytesIO()
    target_pdf.save(output_stream)

    # Reset the position of the output stream to the start
    output_stream.seek(0)
    
    # Translate the title
    file_name_without_extension = os.path.basename(prefix)
    target_language = prefix.split('/')[0]
    source_language = prefix.split('/')[1]
    translated_title = translate_doc_title(file_name_without_extension, target_language, source_language)

    try:
        # Upload the merged PDF to blob storage
        now = datetime.now()
        datetime_string = now.strftime('%Y%m%d%H%M%S')
        final_container_client = blob_service_client.get_container_client(final_container)
        output_blob_name = f"{prefix} ({translated_title})-{datetime_string}.pdf"
        output_blob_client = final_container_client.get_blob_client(output_blob_name)
        output_blob_client.upload_blob(output_stream, blob_type="BlockBlob", overwrite=True)
        logging.info(f"INFO: Mapped document copied to Final container: {output_blob_name}")
        target_pdf.close()
        
    except Exception as e:
        logging.error(f"ERROR: Error copying mapped document ({output_blob_name}) to Final container {e}")
        
            

def translate_doc_title(title, target_language, source_language):
    endpoint = os.environ["text_translator_endpoint"] + "translate"
    subscription_key = os.environ["translator_key"]
    
    headers = {
        'Ocp-Apim-Subscription-Key': subscription_key,
        'Content-type': 'application/json',
        'Accept': 'application/json'
    }
    
    # if source language is unknown, use auto detect.  don't specify "from"
    if source_language == "other":
         params = {
            'api-version': '3.0',
            'to': target_language
        }
    else:
        params = {
            'api-version': '3.0',
            'from': source_language,
            'to': target_language
        }
    
    no_underscore_title = title.replace("_", " ")
    body = [{
        'text': no_underscore_title
    }]
    try:
        response = requests.post(endpoint, headers=headers, params=params, json=body)
        response.raise_for_status()  # Raises an HTTPError if the HTTP request returned an unsuccessful status code
    except Exception as e:
        logging.error(f"ERROR: Error during translation. {e}")

    # The response will contain the translations for the given text in all target languages
    translated_title = response.json()[0]['translations'][0]['text']

    return translated_title

        
def merge_pdfs_in_blob_storage(document_storage_connstr, final_container, translated_container, incoming_blob_name):
    #translated parts can arrive in any order, so check for Final and see if the count matches
    blob_service_client = BlobServiceClient.from_connection_string(document_storage_connstr)
    blob_container_client = blob_service_client.get_container_client(translated_container)
    blob_generator = blob_container_client.list_blobs()
    # Convert the generator to a list
    blob_list = list(blob_generator)
    # Sort the list in alphabetical order by blob name
    blob_list.sort(key=lambda x: x.name)
    
    prefix = get_document_prefix(incoming_blob_name, translated_container)
    
    blob_names = []
    for blob in blob_list:
        if blob.name.startswith(prefix) and not blob.name.endswith("--CustDocTranslatorProcessed.txt"):
            blob_names.append(blob)
    
    if len(blob_names) > 0:        
        blob_service_client = BlobServiceClient.from_connection_string(document_storage_connstr)
        translated_container_client = blob_service_client.get_container_client(translated_container)

        # Create an empty PDF
        pdf_writer = fitz.open()

        # Download the blobs in order and add them to the fitz PDF object
        for blob_name in blob_names:
            translated_blob_client = translated_container_client.get_blob_client(blob_name)
            blob_data = translated_blob_client.download_blob().readall()
            blob_stream = io.BytesIO(blob_data)

            # Load the PDF data from the stream
            pdf = fitz.open(stream=blob_stream.getvalue(), filetype='pdf')
            
             # Add all the pages of the part file to the merged PDF
            pdf_writer.insert_pdf(pdf)

            # Close the part file
            pdf.close()
        

        # Write the merged PDF to a BytesIO object
        output_stream = io.BytesIO()
        pdf_writer.save(output_stream)

        # Reset the position of the output stream to the start
        output_stream.seek(0)
        
        
        # Translate the title
        file_name_without_extension = os.path.basename(prefix)
        target_language = prefix.split('/')[0]
        source_language = prefix.split('/')[1]
        translated_title = translate_doc_title(file_name_without_extension, target_language, source_language)

        # Upload the merged PDF to blob storage
        now = datetime.now()
        datetime_string = now.strftime('%Y%m%d%H%M%S')
        final_container_client = blob_service_client.get_container_client(final_container)
        output_blob_name = f"{prefix} ({translated_title})-{datetime_string}.pdf"
        output_blob_client = final_container_client.get_blob_client(output_blob_name)
        try:
            output_blob_client.upload_blob(output_stream, blob_type="BlockBlob", overwrite=True)
            logging.info(f"INFO: Merged document copied to Final container: {output_blob_name}")
        except Exception as e:
            logging.error(f"ERROR: Error copying merged document ({output_blob_name}) to Final container {e}")

        pdf_writer.close()
        
    
def get_document_prefix(blob_name, translated_container):
    global is_image_file
    global is_single_file
    global is_multi_part_file
    global is_original_file
    global is_mapping_file
    
    prefix = ""
    positionPart = 0    
   
    
    #prefix = translated/uk/en/....
    filename = unquote(blob_name)
    #remove container name "translated/"
    filename = filename.replace("/" + translated_container + "/", "")
    
    if is_image_file:
        positionPart = filename.index("--CustDocTranslatorImageFile.pdf")
    elif is_original_file:
        positionPart = filename.index("--CustDocTranslatorOriginal.pdf")
    elif is_multi_part_file :
        positionPart = filename.index("--CustDocTranslatorScannedPart-")
    elif is_single_file:
        positionPart = filename.index("--CustDocTranslatorSingleFile")
    elif is_mapping_file:
        positionPart = filename.index("--CustDocTranslatorMapping.csv")
    else:
        positionPart = filename.index(".pdf")
   
    try:
        prefix = filename[0 : positionPart]
    except Exception as e:
        print(f"ERROR: get_document_prefix for document: {blob_name}.  Message: {e}")
        logging.error(f"ERROR: get_document_prefix for document: {blob_name}.  Message: {e}")
        
    return prefix
    


def get_total_parts(blob_name):
    total_parts = 0
    if blob_name.endswith("-Final.pdf"):
        positionPart = blob_name.index("--CustDocTranslatorScannedPart-")
        positionFinal = blob_name.index("-Final.pdf")
        endPositionPart = positionPart + 15
        try:
             total_parts = blob_name[endPositionPart : positionFinal]
             print(f"total_parts: {total_parts}")
             total_parts = int(total_parts)
        except Exception as e:
            print(f"ERROR: get_total_parts for document: {blob_name}.  Message: {e}")
            logging.error(f"ERROR: get_total_parts for document: {blob_name}.  Message: {e}")
            total_parts = 0
            
    return total_parts
    

def clean_up_working_files(document_storage_connstr, converted_container, translated_container, incoming_blob_name):
    global is_mapping_file
    global is_multi_part_file
    global mapping_file_container
    
    blob_service_client = BlobServiceClient.from_connection_string(document_storage_connstr)
    translated_container_client = blob_service_client.get_container_client(translated_container)
    translated_blob_list = translated_container_client.list_blobs()
    converted_container_client = blob_service_client.get_container_client(converted_container)
    converted_blob_list = converted_container_client.list_blobs()
    
    prefix = get_document_prefix(incoming_blob_name, translated_container)
        
        
    if is_mapping_file:
        file_extension = "pdf"
        # delete the mapping file .csv file in mapping container
        mapping_container_client = blob_service_client.get_container_client(mapping_file_container)
        prefix = prefix.replace("/" + mapping_file_container + "/", "")
        mapping_blob_client = mapping_container_client.get_blob_client(prefix + "--CustDocTranslatorMapping.csv")
        try:
            mapping_blob_client.delete_blob()
        except Exception as e:
            logging.error(f"ERROR: Error deleting mapping file: File: {prefix}--CustDocTranslatorMapping.csv  ERRMSG: {e}")
        
        # delete the processed file in translated container, change container from mapping to translated
        blob_client = translated_container_client.get_blob_client(prefix + "--CustDocTranslatorProcessed.txt")
        try:
            blob_client.delete_blob()
        except Exception as e:
            logging.error(f"ERROR: Error deleting processed file: File: {prefix}--CustDocTranslatorProcessed.txt  ERRMSG: {e}")
    else:
        file_extension = incoming_blob_name.split('.')[-1]
        
    
    for blob in translated_blob_list:
        if blob.name.startswith(prefix) and (blob.name.endswith(file_extension) or blob.name.endswith("--CustDocTranslatorProcessed.txt")) and not blob.name.endswith("--CustDocTranslatorOriginal.pdf"):
           blob_client = translated_container_client.get_blob_client(blob.name)
           try:
               blob_client.delete_blob()
           except Exception as e:
               logging.error(f"ERROR: Error deleting file: File: {blob.name}  ERRMSG: {e}")  
        elif blob.name.startswith(prefix) and blob.name.endswith("--CustDocTranslatorOriginal.pdf"):
            blob_client = translated_container_client.get_blob_client(blob.name)
            try:
                blob_client.delete_blob()
            except Exception as e:
                logging.error(f"ERROR: Error deleting file: File: {blob.name}  ERRMSG: {e}")         
           
    for blob in converted_blob_list:
        if blob.name.startswith(prefix) and blob.name.endswith(file_extension):
           blob_client = converted_container_client.get_blob_client(blob.name)
           try:
               blob_client.delete_blob()
           except Exception as e:
               logging.error(f"ERROR: Error deleting file: File: {blob.name}  ERRMSG: {e}")
               
    

     
       
def identify_part_files(folder_path): 
    # Get a list of all files in the folder
    files = os.listdir(folder_path)

    # Dictionary to store main files and their corresponding part files
    main_files = {}

    # Regular expression pattern to match the main file prefix
    pattern = r"^(.*)-Part\d+\.pdf$"

    # Iterate over the files in the folder
    for file_name in files:
        # Match the pattern to extract the main file prefix
        match = re.match(pattern, file_name)
        if match:
            main_file_prefix = match.group(1)
            # Add the file to the corresponding main file in the dictionary
            main_files.setdefault(main_file_prefix, []).append(file_name)

    return main_files

def merge_part_files(folder_path, main_files):
    for main_file, part_files in main_files.items():
        # Create a new PDF document
        merged_pdf = fitz.open()

        # Sort the part files based on their numerical order
        part_files.sort(key=lambda x: int(re.search(r"Part(\d+)", x).group(1)))

        for part_file in part_files:
            # Open the part file
            pdf = fitz.open(os.path.join(folder_path, part_file))

            # Add all the pages of the part file to the merged PDF
            merged_pdf.insert_pdf(pdf)

            # Close the part file
            pdf.close()

        # Save the merged PDF to a file
        merged_pdf.save(os.path.join(folder_path, f"{main_file}-Final.pdf"))

        # Close the merged PDF
        merged_pdf.close()

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

def copy_file_to_final(document_storage_connstr, final_container, translated_container, incoming_blob_name):
    #copy the original doc to output folder
    blob_service_client = BlobServiceClient.from_connection_string(document_storage_connstr)
    now = datetime.now()
    datetime_string = now.strftime('%Y%m%d%H%M%S')
    filename = unquote(incoming_blob_name)
    filename_array = filename.replace("/" + translated_container + "/", "").split('.')
    file_type=filename_array[1].lower()
    file_name=filename_array[0]

    source_blob = blob_service_client.get_blob_client(translated_container, filename.replace("/" + translated_container + "/", ""))
    
    # Translate the title
    prefix = get_document_prefix(incoming_blob_name, translated_container)
    file_name_without_extension = os.path.basename(prefix)
    file_extenstion = os.path.splitext(incoming_blob_name)[1][1:]
    target_language = prefix.split('/')[0]
    source_language = prefix.split('/')[1]
    translated_title = translate_doc_title(file_name_without_extension, target_language, source_language)
    
    #remove image/single file tag
    file_name = file_name.replace("--CustDocTranslatorImageFile", "")
    file_name = file_name.replace("--CustDocTranslatorSingleFile", "")
    
    output_blob_name = f"{prefix} ({translated_title})-{datetime_string}.{file_extenstion}"  

    destination_blob = blob_service_client.get_blob_client(final_container, output_blob_name)

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
                logging.info(f'INFO: File {incoming_blob_name} copied successfully to container {final_container} as {output_blob_name}')
        else:
            logging.error(f"ERROR: Blob copy failed with status: {copy_status}.")
            
    except Exception as e:
        logging.error(f"ERROR: An error occured when copying file: {e}")
