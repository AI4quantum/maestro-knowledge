# Notes from testing with LLMs

Combination of notes from reviewing as end user, and supported by LLM interaction

granite-4-tiny-h Q4_K_M

### 1. List of tools is confusing (User)

cleanup
count_documents
create_collection
delete_collection
delete_document
delete_document_from_collection
delete_documents
get_collection_info
get_database_info
get_document
get_supported_chunking_strategies
get_supported_embeddings
list_collections
list_databases
list_documents
list_documents_in_collection
query
register_database
resync_databases_tool
search
setup_database
write_document
write_document_to_collection
write_documents

Individual tools do have more specific docs, however at a high level there is still some confusion here:

* What is register vs setup. I would expect to automatically pick up databases/collections available in the backend. Then I would expect a 'create database' ? 
* What is 'cleanup' why not a delete database
* Why 3 different delete_document variations? Don't we always delete from a collection? Should we combine the multiple with single? This also applies to write_document and its variations. And list too
* resync_databases_tool - awkward name. it's a weird admin command. Can we name it better (it should only be needed if the backend changes without us knowing. maybe it's just a refresh?)
* get supported chunking strategies and get_supported_chunking strategies both seem config related. Maybe a get_config would be better? And cover both? Or at least be named get_config_chunking etc? (seems less clear though)
* Why do we gave a get_document, but a get_collection_info and get_database_info - can we keep the naming consistent? 
* How is query different to list_documents or get_document? IMO list should just give minimal info ie metadata whilst get_document returns. Maybe query is the 'ultimate' endpoint that can handle different object types or take a very different form of expression. Need to be clear on the value.
* Use singular/plural consistently
* need to consider intent. When do we get/list chunks (which are really the individual document in the repo) vs the full document? For example does get_document get the full content across all chunks, whilst query does a search across fragments. discuss!

## 2. is there a default database

When I login with a milvus UI, attu, I see a 'default' database listed, yet our list_databases() says there are no databases. The mcp tool does let me create a database called 'default' then shows it. Is this just an Attu anomoly?

## 3. Why is there a default collection 'Maestro Docs'

After creating a new database, a call to list_databases() shows that we have a default database with a collection 'Maestro Docs'
- Is it confusing to add a default collection
- when we list databases why does it show the collection at all? I might expect that from a list_collections or similar? Or at least return a structure with the collection embedded. Are we confused about the relationship between a database and a collection?

## 4. MaestroDocs Collection doesn't actually exist

After creating the new database (which seemed to report, as above, that it had created a collection), a list_collections() reported that no collections were found

## NOTE: these things worked

Note that I was able to explicitly call create_collection() with 'mydocs' which worked fine, and list_collection correctly reported it existed. It showed up in attu ok

delete_collection also correctly deleted my collection, and attu no longer shows it

I was also able to delete the database (it called cleanup() ) and trying to list databases/collections showed that none existed. Attu did still show the database, but I think this is covered by 2 above

## 5. Deletions are too easy

For deleting a collection, or a database, I think it would be useful to have a 'force' parameter so a default delete only does so if empty? Unless force is provided? It could even report how many docs or chunks are present? or number of collections if deleting a database

## 6. Embedding info - how useful

calling the embedding tool gives me

[
  {
    "type": "text",
    "text": "Supported embeddings for milvus vector database 'default': [\n  \"default\",\n  \"text-embedding-ada-002\",\n  \"text-embedding-3-small\",\n  \"text-embedding-3-large\",\n  \"custom_local\"\n]\n\nNOTE: The default 'auto' setting automatically selects the best embedding from your environment configuration."
  }
]
It would be helpful if it could elaborate on what custom_local maps to - could we extract and return this maybe as an additional object as the backend knows the details

## 7. Text vs json responses

Our tools typically return text. Even when they include embedded json - such as the item above? What's the recommended pattern. Return text or json? which is more actionable for models? Should we always include both text and structured json (ie all in the json response - but the description being just text). Can this be consistent across all API calls

## 8. default chunking strategy

After creating a collection and then querying what chunking was used - the answer was none. This is not a good default. Going with a sentence based (or else) fixed strategy seems more scalable and natural. Consider a back end environment variable to define the default chunking strategy/size

If chunking strategy needs to be consistent in a collection, clarify it cannot be changed later. If it needs to be changed, it needs to be done at collection creation time. (Advise if this is an incorrect limitation?)

Additionally requesting the model change the chunking strategy resulted in

Failed to parse arguments for tool "create_collection": params.chunking_config is not any of [subschema 0],[subschema 1]

{"name": "create_collection", "arguments": {"database": "default", "collection": "mydocs", "chunking_config": "{\"strategy\":\"Sentence\",\"parameters\":{\"overlap\":1}}"}}

In fact even when creating a new collection it was not possible to specify the chunking strategy at all which is a critical error (given our poor default)

granite-4-tiny did try a few times with

Model failed to generate a tool call

Failed to parse arguments for tool "create_collection": params.chunking_config is not any of [subschema 0],[subschema 1]

{"name": "create_collection", "arguments": {"database": "default", "collection": "docs", "chunking_config": "{\"strategy\":\"Sentence\",\"parameters\":{\"chunk_size\":256,\"overlap\":128}}"}}

It may be struggling with nested json?

## 9. Count vs get_collection_info

Doesn't the ability to get information about a collection include the document count? Is it worth keeping both or does it add complexity?

# 10. write_document assumes MaestroDocs

write_document assumes the collection MaestroDocs. We don't have one, just a 'mydocs' collection in an example I tried. This relates to item 3 and 4 earlier

# 11. URL parameter when creating docs

When the LLM tried to create a doc within a collection if floundered on


Failed to parse arguments for tool "write_document_to_collection": params requires property "url"

{"name": "write_document_to_collection", "arguments": {"database": "default", "collection": "mydocs", "document_name": "", "text": "British history is a rich tapestry … (full text continues as above) … Today, Britain remains a constitutional monarchy…"}}

It then suggested using write_documents where a url isn't required!

This should be consistent across writes (see 1). Which of a document name, identifier, pathname is mandatory. Be clear and enforce consistently. THere must be at least one key to support deletion, list etc. Ensure the mcp comments used by the agent are clear. We may want to refer to URI if that's a better term (again, consistently)

# 12. Document name when creating docs

Arguments

database:

default

collection:

mydocs

document_name:

text:

British history is a rich tapestry … (full text continues as above) … Today, Britain remains a constitutional monarchy…
url:

https://example.com/british-history-001
Result

[
  {
    "type": "text",
    "text": "{\n  \"status\": \"error\",\n  \"message\": \"Error: dictionary update sequence element #0 has length 1; 2 is required\"\n}"
  }
]

This confused the llm - it did figure out a document name was required, but the error message should be improved. refer to parameter by name!

See also 11 as we need to clarify mandatory vs optional. Perhaps a document name and a URL are mandatory?

#13. Unable to write documents to a collection

Ultimately attempts to write a document failed

write_document_to_collection
({"database":"default","collection":"mydocs","docum…})

mcp/maestro-knowledge

Arguments

database:

default

collection:

mydocs

document_name:

british_history_001

url:

https://example.com/british-history-001
text:

British history is a rich tapestry … (full text continues as above) … Today, Britain remains a constitutional monarchy…
Result

[
  {
    "type": "text",
    "text": "{\n  \"status\": \"error\",\n  \"message\": \"Error: dictionary update sequence element #0 has length 1; 2 is required\"\n}"
  }
]

# 13. list_documents still refers to old name

Model failed to generate a tool call

Failed to parse arguments for tool "list_documents": params requires property "database"

{"name": "list_documents", "arguments": {"database_name": "default"}}

Oddly the database_name is an old parameter name. We need to check all comments (and errors) in the mcp server in case we are misleading the agent with outdated information

# 14. List documents in database - what does it mean

There's a list_documents tool that attempts to return a list of documents in a database. However given that we have multiple collections this seems to incorrectly flatten that structure