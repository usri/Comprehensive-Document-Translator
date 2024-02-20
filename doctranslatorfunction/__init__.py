import csv
import io
import logging
import os
from urllib.parse import unquote, urlparse
from venv import logger
from azure.core.credentials import AzureKeyCredential
from azure.ai.translation.document import DocumentTranslationClient, TranslationGlossary
import azure.functions as func
from azure.storage.blob import BlobServiceClient

from  tenacity import retry, stop_after_attempt, wait_exponential
import logging
import json
import fitz

import azure.functions as func


endpoint = os.environ["translator_endpoint"]
key = os.environ["translator_key"]

document_storage_connstr = os.environ["document_storage_connstr"]
document_storage = os.environ["document_storage"]
translated_container = os.environ["translated_container"]
target_blob_url = document_storage + "/" + translated_container

glossary_connstr = os.environ["glossary_connstr"]
glossary_storage = os.environ["glossary_storage"]
glossary_container = os.environ["glossary_container"]

translated_container = os.environ["translated_container"]
mapping_file_container = os.environ["mapping_file_container"]



def main(msg: func.QueueMessage, outputQueueItem: func.Out[str]) -> None:
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

    logging.info(result)
    
    decoded_msg = json.loads(result)
    decoded_body = json.loads(decoded_msg['body'])
    file_name = decoded_body['file_name']
    
    if(len(decoded_body) > 0): 
       
        target_language= decoded_body['target_language']
        source_language= decoded_body['source_language']
        source_blob_url = decoded_body['blob_url']
        glossary_name = source_language + "-" + target_language + ".tsv"
        glossary_url = glossary_storage + "/" + glossary_container + "/" + glossary_name
       

        #Check if target_blob_url already exists.  If so, delete it.  Note: this could change depending on what customer wants to do
        if check_if_file_exists(document_storage_connstr, translated_container, source_blob_url, target_language, source_language):
            logging.warning("WARNING: Translated file already exists. It will be deleted and replace by new version.")
            try:
                delete_file(document_storage_connstr, translated_container, source_blob_url, target_language, source_language)
            except:
                logging.error("ERROR: Unable to delete existing translated file")
            finally:
                logging.info("INFO: Existing translated file was deleted and will be replaced by new version.")
        

        client = DocumentTranslationClient(endpoint, AzureKeyCredential(key))
        logging.info("INFO: Begin Translation for: " + file_name)
        
        #Check if glossaries file exists - if source language is not "other"
        #If source_language is "other", then set source_language_name to "none" and glossary_name to "none"
        if source_language == "other":
            try:
                logging.info(f"INFO: Source Language = {source_language}. Before calling Translator Service for {source_blob_url}")
                start_translation(client, 
                                        source_blob_url,
                                        target_blob_url,  
                                        target_language,
                                        source_language,
                                        file_name)
                #if final part then add message to queueforaggregations
                #outputQueueItem.set(f"{source_blob_url}")
               
                
            except Exception as e:
                logging.error(f"ERROR: Translation failed for {source_blob_url}. {e}")
                print(f"ERROR: Translation failed for {source_blob_url}. {e}")
        else:
                if check_glossary_exists(glossary_connstr, glossary_container, glossary_name):
                    logging.info(f"INFO: Glossary file exists.  Before calling Translator Service for {source_blob_url}")
                    try:
                        start_translation(client, 
                                            source_blob_url,
                                            target_blob_url,  
                                            target_language,
                                            source_language,
                                            file_name, 
                                            glossary_url)
                        
                        # check if all parts exists before adding to queueforaggregations
                        # don't add to queueforaggregations if the file is --CustDocTranslatorOriginal.pdf
                        #outputQueueItem.set(f"{source_blob_url}")
                            
                    except Exception as e:
                        logging.error(f"ERROR: Translation failed for {source_blob_url}. {e}")
                        print(f"ERROR: Translation failed for {source_blob_url}. {e}")
                    
                   
                else:
                    logging.info(f"INFO: Glossary file does not exist.  Before calling Translator Service for {source_blob_url}")
                    try:
                        start_translation(client, 
                                            source_blob_url,
                                            target_blob_url,  
                                            target_language,
                                            source_language,
                                            file_name)
                        
                        #if image, single file, or final part then add message to queueforaggregations
                            
                    except Exception as e:
                        logging.error(f"ERROR: Translation failed for {source_blob_url}. {e}")
                        print(f"ERROR: Translation failed for {source_blob_url}. {e}")
         
        # Write to queueforaggregation if valid file
        url_for_message = get_url_and_validate_for_queue(file_name, target_blob_url)   
        if url_for_message is not None:
            outputQueueItem.set(f"{url_for_message}")
            url_for_message = None

    else:
        logging.error("ERROR: No message body found in queuefortranslation message.")
        raise Exception("ERROR: No message body found in queuefortranslation message.")
    
 
#validate if file is ready for queueforaggregation, return Url for message
def get_url_and_validate_for_queue(file_name, target_blob_url):
    
    # check if all parts exists before adding to queueforaggregations
    # don't add to queueforaggregations if the file is --CustDocTranslatorOriginal.pdf
    is_valid_for_queueforaggregation = False
    
    final_file_url = ""
    if "--CustDocTranslatorScannedPart-" in file_name:
        is_multi_part_file = True
    else:
        is_multi_part_file = False
    
    # if is_mapped_file, then only send (filename)--CustDocTranslatorMapping.csv to queueforaggregation
    mapping_file_url = ""
    
    if "--CustDocTranslatorMappedScannedPart-" in file_name or "--CustDocTranslatorMappedTextOnlyPages.pdf" in file_name:
        is_mapped_file = True
    else:
        is_mapped_file = False
        
    # image files are not split into parts
    if "--CustDocTranslatorImageFile.pdf" in file_name or "--CustDocTranslatorOriginal.pdf" in file_name or "--CustDocTranslatorSingleFile" in file_name:
        is_valid_for_queueforaggregation = True
        
        
    # if multipart, then check if all parts exists before adding to queueforaggregations
    # create flag file in translated container to prevent duplicate processing
    elif is_multi_part_file:
        if check_all_parts_complete(file_name):
            if prevent_duplicate_processing(file_name):
                final_file_blob = get_file_blob(file_name, "final")
                if final_file_blob is not None:
                    final_file_url = target_blob_url + "/" + final_file_blob.name
                    is_valid_for_queueforaggregation = True
                    
    # if mapped file, then check if mapping file exists before adding to queueforaggregations
    # create flag file in translated container to prevent duplicate processing
    elif is_mapped_file:
        #Open the CSV file and validate that all listed pdfs are in the translated container
        if validate_mapped_files_exist(document_storage_connstr, translated_container, file_name):
            if prevent_duplicate_processing(file_name):
                mapping_file_blob = get_file_blob(file_name, "mapping")
                if mapping_file_blob is not None:
                    mapping_file_url = target_blob_url.replace("/translated", "/mapping") + "/" + mapping_file_blob.name
                    is_valid_for_queueforaggregation = True
        
    if is_valid_for_queueforaggregation:
        if is_multi_part_file:
            logging.info(f"INFO: Added {final_file_url} to queueforaggregation")
            return final_file_url
        elif is_mapped_file:
            logging.info(f"INFO: Added {mapping_file_url} to queueforaggregation")
            return mapping_file_url
        else:
            logging.info(f"INFO: Added {target_blob_url} to queueforaggregation")
            return target_blob_url + "/" + file_name
            



def validate_mapped_files_exist(document_storage_connstr, translated_container, incoming_file_url):
    global mapping_file_container
    file_map_array = []
    
    all_mapped_files_exist = True
    
    #get the prefix for the file, then get the mapping file from the mapping container
    
    prefix = get_document_prefix(incoming_file_url, translated_container)
    
    map_csv_file = prefix + "--CustDocTranslatorMapping.csv"
    
    
    try:
        blob_service_client = BlobServiceClient.from_connection_string(document_storage_connstr)
        mapping_container_client = blob_service_client.get_container_client(mapping_file_container)
        map_data = io.BytesIO()
        csv_file_exists = False
        mapping_csv_blob_client = mapping_container_client.get_blob_client(map_csv_file)
        try:
            mapping_csv_blob_client.get_blob_properties()
            csv_file_exists = True
        except Exception as e:
            all_mapped_files_exist = False
        
        if csv_file_exists:
            try:
                blob_data = mapping_container_client.download_blob(map_csv_file)
                blob_data.readinto(map_data)
                map_data.seek(0)
                csv_reader = csv.reader(io.StringIO(map_data.getvalue().decode('utf-8')))
                file_map_array = [row for row in csv_reader]
                already_checked = []
                for file_map in file_map_array:
                    if len(file_map) == 3:
                        source_pdf_name = file_map[1]
                        if not source_pdf_name in already_checked:
                            translated_container_client = blob_service_client.get_container_client(translated_container)
                            translated_blob_client = translated_container_client.get_blob_client(source_pdf_name)
                            try:
                                translated_blob_client.get_blob_properties()
                                already_checked.append(source_pdf_name)
                                logging.info(f"INFO: map_files_to_final - Mapped pdf exists. PDF: {source_pdf_name}")
                            except Exception as e:
                                logging.warning(f"INFO: map_files_to_final - Mapped pdf does not exist yet. PDF: {source_pdf_name}  ERRMSG: {e}")
                                all_mapped_files_exist = False
                        else:
                            logging.warning(f"INFO: map_files_to_final - Already checked pdf, no need to open. Move to next file. PDF: {source_pdf_name}")
            except Exception as e:
                logging.error(f"ERROR: map_files_to_final - Error downloading mapping file. File: {map_csv_file} {e}")
                all_mapped_files_exist = False
        else:
            logging.warning(f"INFO: map_files_to_final - Mapping CSV file does not exist yet. File: {map_csv_file}")
            all_mapped_files_exist = False
                
    except Exception as e:
        logging.error(f"ERROR: Error during validate_mapped_files_exist. {e}")
        all_mapped_files_exist = False
    
    
                
    return all_mapped_files_exist


 
def prevent_duplicate_processing(file_name):
    blob_service_client = BlobServiceClient.from_connection_string(document_storage_connstr)
    blob_container_client = blob_service_client.get_container_client(translated_container)
    blob_list = blob_container_client.list_blobs()
    
    prefix = get_document_prefix(file_name, translated_container)
    flag_file_name = prefix + "--CustDocTranslatorProcessed.txt"
    
    for blob in blob_list:
        if blob.name.lower() == flag_file_name.lower():
            return False
        
    blob_client = blob_container_client.get_blob_client(flag_file_name)
    try:
        blob_client.upload_blob("processed")
        return True
    except Exception as e:
        logging.error(f"ERROR: Error occurred when trying to create flag file: {e}")
    


def get_file_blob(source_blob_url, file_type):
    blob_service_client = BlobServiceClient.from_connection_string(document_storage_connstr)
    
    if file_type == "mapping":
        blob_container_client = blob_service_client.get_container_client(mapping_file_container)
    elif file_type == "final":
        blob_container_client = blob_service_client.get_container_client(translated_container)
        
    blob_list = blob_container_client.list_blobs()
    prefix = get_document_prefix(source_blob_url, translated_container)
    
    for blob in blob_list:
        if file_type == "mapping":
            if blob.name.startswith(prefix) and blob.name.endswith("--CustDocTranslatorMapping.csv"):
                return blob
        elif file_type == "final":
            if blob.name.startswith(prefix) and blob.name.endswith("-Final.pdf"):
                return blob
    
    return None
    

def check_all_parts_complete(incoming_blob_name):
    
    #translated parts can arrive in any order, so check for Final and see if the count matches
    blob_service_client = BlobServiceClient.from_connection_string(document_storage_connstr)
    blob_container_client = blob_service_client.get_container_client(translated_container)
    blob_list = blob_container_client.list_blobs()
    
    prefix = get_document_prefix(incoming_blob_name, translated_container)
        
    matching_prefix_count = 0
    total_parts = 0
    for blob in blob_list:
        if blob.name.startswith(prefix):
            matching_prefix_count += 1
            print(f"matching_prefix_count: {matching_prefix_count}")
            
        if  blob.name.startswith(prefix) and blob.name.endswith("-Final.pdf"):
            total_parts = get_total_parts(blob.name)
        
    if total_parts > 0 and matching_prefix_count == total_parts:
        return True
    elif blob.name.endswith("--CustDocTranslatorImageFile.pdf"):
        return True
    elif "--CustDocTranslatorSingleFile" in blob.name:
        return True
    elif blob.name.endswith("--CustDocTranslatorOriginal.pdf"):
        return True
    else:
        return False
    
def get_document_prefix(blob_name, translated_container):
    is_image_file = False
    is_single_file = False
    is_multi_part_file = False
    is_mapped_scanned_file = False
    is_mapped_text_only_file = False
    is_original_file = False
    
    if "--CustDocTranslatorImageFile.pdf" in blob_name:
        is_image_file = True
        
    if "--CustDocTranslatorSingleFile" in blob_name:
        is_single_file = True

    if "--CustDocTranslatorScannedPart-" in blob_name:
        is_multi_part_file = True
        
    if "--CustDocTranslatorMappedScannedPart-" in blob_name:
        is_mapped_scanned_file = True
    
    if blob_name.endswith("--CustDocTranslatorMappedTextOnlyPages.pdf"):
        is_mapped_text_only_file = True
        
    if "--CustDocTranslatorOriginal.pdf" in blob_name:
        is_original_file = True


    prefix = ""
    positionPart = 0    
    
    #prefix = translated/uk/en/....
    filename = unquote(blob_name)
    #remove container name "translated/"
    #filename = filename.replace("/" + translated_container + "/", "")
    
    if is_image_file:
        positionPart = filename.index("--CustDocTranslatorImageFile.pdf")
    elif is_original_file:
        positionPart = filename.index("--CustDocTranslatorOriginal.pdf")
    elif is_multi_part_file :
        positionPart = filename.index("--CustDocTranslatorScannedPart-")
    elif is_single_file:
        positionPart = filename.index("--CustDocTranslatorSingleFile")
    elif is_mapped_scanned_file:
        positionPart = filename.index("--CustDocTranslatorMappedScannedPart-")
    elif is_mapped_text_only_file:
        positionPart = filename.index("--CustDocTranslatorMappedTextOnlyPages.pdf")
    else:
        positionPart = filename.index(".pdf")
   
    try:
        prefix = filename[0 : positionPart]
    except Exception as e:
        print(f"ERROR: get_document_prefix for document: {blob_name}.  Message: {e}")
        logging.error(f"ERROR: get_document_prefix for document: {blob_name}.  Message: {e}")
        
    return prefix

def get_total_parts(blob_name):
    is_mapped_file = False
    if "--CustDocTranslatorMappedScannedPart-" in blob_name:
        is_mapped_file = True
    
    total_parts = 0
    if blob_name.endswith("-Final.pdf"):
        if is_mapped_file:
            strSuffix = "--CustDocTranslatorMappedScannedPart-"
            positionPart = blob_name.index(strSuffix)
            endPositionPart = positionPart + len(strSuffix)
        else:
            strSuffix = "--CustDocTranslatorScannedPart-"
            positionPart = blob_name.index(strSuffix)
            endPositionPart = positionPart + len(strSuffix)
            
        positionFinal = blob_name.index("-Final.pdf")
       
        try:
             total_parts = blob_name[endPositionPart : positionFinal]
             print(f"total_parts: {total_parts}")
             total_parts = int(total_parts)
        except Exception as e:
            print(f"ERROR: get_total_parts for document: {blob_name}.  Message: {e}")
            logging.error(f"ERROR: get_total_parts for document: {blob_name}.  Message: {e}")
            total_parts = 0
            
    return total_parts
    

# Define the retry parameters
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
def start_translation(client, source_blob_url, target_blob_url, target_language, source_language, file_name, glossary_url=None):
    logging.info(f"INFO: start_translation method. Before calling Translator Service for {source_blob_url}")
    if source_language == "other":
        logging.info(f"INFO: Source Language = {source_language}. Before calling Translator Service for {source_blob_url}")
        poller =  client.begin_translation(source_blob_url, 
                                        target_blob_url,  
                                        target_language,
                                        storage_type="File")
        
    elif source_language != "other" and glossary_url is None:
        poller =  client.begin_translation(source_blob_url, 
                                        target_blob_url,  
                                        target_language,
                                        source_language, 
                                        storage_type="File")        
        
    elif source_language != "other" and glossary_url is not None:
        logging.info(f"INFO: Source Language: {source_language}. Before calling Translator Service for {source_blob_url}")
        poller = client.begin_translation(source_blob_url,
                                        target_blob_url,  
                                        target_language,
                                        source_language, 
                                        storage_type="File",
                                        glossaries=[TranslationGlossary(glossary_url, file_format="TSV")])
        
    logging.info(f"INFO: Created translation operation with ID: {poller.id}")
    logging.info("INFO: Waiting until translation completes...")
    result = poller.result()

    for document in result:
        logging.info(f"Document ID: {document.id}")
        logging.info(f"Document status: {document.status}")
        if document.status == "Succeeded":
            logging.info(f"INFO: Source document location: {document.source_document_url}")
            logging.info(f"INFO: Translated document location: {document.translated_document_url}")
            logging.info(f"INFO: Translated to language: {document.translated_to}\n")
            
           
        else:
            logging.error(f"Error Code: {document.error.code}, Message: {document.error.message}\n")
            if document.error.code == "NoTranslatableText":
                #copy file to translated container                
                blob_service_client = BlobServiceClient.from_connection_string(document_storage_connstr)
                translated_container_client = blob_service_client.get_container_client(translated_container)
                blob_client = translated_container_client.get_blob_client(file_name)
                blob_client.start_copy_from_url(source_blob_url)
                logging.info(f"INFO: NoTranslatableText for Document Id: {document.id}  FileName: {file_name}")
               
        
#check if .tsv glossary files exist
def check_glossary_exists(document_storage_connstr, glossary_container, glossary_name):
    
    blob_service_client = BlobServiceClient.from_connection_string(document_storage_connstr)
    blob_container_client = blob_service_client.get_container_client(glossary_container)
    blob_list = blob_container_client.list_blobs()
    
    for blob in blob_list:
        if blob.name.lower() == glossary_name.lower() :
            return True
        else:
            return False
        
     
        
def check_if_file_exists(document_storage_connstr, translated_container, source_blob_url, target_language, source_language):
    
    blob_service_client = BlobServiceClient.from_connection_string(document_storage_connstr)
    blob_container_client = blob_service_client.get_container_client(translated_container)
    
    parsed_url = urlparse(source_blob_url)
    filename = target_language + "/" + source_language + "/" + os.path.basename(parsed_url.path)
    
    blob_list = blob_container_client.list_blobs()
    for blob in blob_list:
        #unquote does html decoding
        if blob.name.lower() == unquote(filename.lower()) :
            return True
        
    #No file match, file does not exist
    return False
        
        
def delete_file(document_storage_connstr, translated_container, source_blob_url, target_language, source_language):
    blob_service_client = BlobServiceClient.from_connection_string(document_storage_connstr)
    blob_container_client = blob_service_client.get_container_client(translated_container)
    parsed_url = urlparse(source_blob_url)
    filename =  target_language + "/" + source_language + "/" + os.path.basename(parsed_url.path)
     #unquote does html decoding
    blob_client = blob_container_client.get_blob_client(unquote(filename))
    
    try:
        blob_client.delete_blob(delete_snapshots="include")
        logging.info("INFO: Existing translated document was deleted.")
    except Exception as e:
        logging.error(f"ERROR: Error occurred when trying to delete file: {e}")
        print(f"ERROR: Error occurred when trying to delete file: {e}")
    
