from hypothesis_jsonschema import from_schema
from hypothesis import given
from genson import SchemaBuilder

# Complex nested JSON with mixed types
complex_data = {
  "results": [
    {
      "house": {
        "name": "the name of the house in English",
        "address": "street name and number, zip code city name",
        "price": 520000,
        "property_type": "one of the enum values 'a', 'b' or 'c'",
        "image_url": "a public url of a image in png or jpg format. **must not** require authentication"
      }
    },
    {
      "house": {
        "name": "Villa les hussards",
        "address": "In the center of the street 3, 8121 Belgere",
        "price": 1000500,
        "property_type": "Contemporary",
        "image_url": "https://commons.wikimedia.org/wiki/Category:Modernist_houses_in_Belgium#/media/File:Belgique_-_Rixensart_-_Villa_les_Hussards_-_01.jpg"
      }
    },
    {
      "house": {
        "name": "Villa Tugendhat",
        "address": "On the crest 4, 8121 Brno",
        "price": 370000,
        "property_type": "Contemporary",
        "image_url": "https://commons.wikimedia.org/wiki/Category:Villa_Tugendhat#/media/File:Vila_Tugendhat_Brno_2016_5.jpg"
      }
    },
    {
      "house": {
        "name": "Futuro Houses",
        "address": "In the middle of nowhere, 8121 Wanli",
        "price": 87700,
        "property_type": "Futuristic",
        "image_url": "https://commons.wikimedia.org/wiki/Category:Futuro#/media/File:Futuro_Village,_Wanli_10.jpg"
      }
    }
  ]
}

def extract_field_descriptions(example_data):
    """Extract descriptions from the first item in the example data array"""
    descriptions = {}

    def process_object(obj, path=""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = f"{path}.{key}" if path else key
                if isinstance(value, dict):
                    process_object(value, current_path)
                elif isinstance(value, list):
                    process_object(value[0] if value else {}, current_path)
                else:
                    descriptions[current_path] = str(value)

    if isinstance(example_data, dict):
        process_object(example_data)
    elif isinstance(example_data, list) and example_data:
        process_object(example_data[0])

    return descriptions

def add_descriptions_to_schema(schema, descriptions, path=""):
    """Add descriptions to schema fields"""
    if isinstance(schema, dict):
        if schema.get('type') == 'object' and 'properties' in schema:
            for prop_name, prop_schema in schema['properties'].items():
                current_path = f"{path}.{prop_name}" if path else prop_name
                if current_path in descriptions:
                    prop_schema['description'] = descriptions[current_path]
                add_descriptions_to_schema(prop_schema, descriptions, current_path)
        elif schema.get('type') == 'array' and 'items' in schema:
            add_descriptions_to_schema(schema['items'], descriptions, path)



# Adding multiple examples helps genson refine the schema
builder = SchemaBuilder()
builder.add_object(complex_data)

schema = builder.to_schema()

# Extract descriptions from first example
descriptions = extract_field_descriptions(complex_data)

# Add descriptions to schema
add_descriptions_to_schema(schema, descriptions)

print(schema)