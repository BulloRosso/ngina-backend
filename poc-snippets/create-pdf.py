import docraptor
import os

# https://docraptor.com/documentation/python
doc_api = docraptor.DocApi()
doc_api.api_client.configuration.username = os.getenv('DOCRAPTOR_API_KEY')
# doc_api.api_client.configuration.debug = True

try:
    response = doc_api.create_doc({
      "test": True,                                                   # test documents are free but watermarked
      "document_content": "<html><body><div style='color: red'>My name is Lucky</span></body></html>",    # supply content directly
      # "document_url": "http://docraptor.com/examples/invoice.html", # or use a url
      "name": "simple-python.pdf",                                 # help you find a document later
      "document_type": "pdf",                                         # pdf or xls or xlsx
      # "javascript": True,                                           # enable JavaScript processing
      # "prince_options": {
      #   "media": "screen",                                          # use screen styles instead of print styles
      #   "baseurl": "http://hello.com",                              # pretend URL when using document_content
      # },
    })

 # create_doc() returns a binary string
    with open('docraptor-hello.pdf', 'w+b') as f:
        binary_formatted_response = bytearray(response)
        f.write(binary_formatted_response)
        f.close()
    print('Successfully created docraptor-hello.pdf!')
  
except docraptor.rest.ApiException as error:
    print(error.status)
    print(error.reason)
    print(error.body)