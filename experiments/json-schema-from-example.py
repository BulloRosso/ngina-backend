from genson import SchemaBuilder

# Complex nested JSON with mixed types
complex_data = {
    "users": [
        {
            "id": 123,
            "profile": {
                "name": "John",
                "addresses": [
                    {"type": "home", "coords": [40.7128, -74.0060]},
                    {"type": "work", "coords": [34.0522, -118.2437]}
                ],
                "metadata": {
                    "lastLogin": "2024-02-23T10:30:00Z",
                    "settings": {"theme": "dark", "notifications": True}
                }
            }
        }
    ],
    "version": "2.0",
    "tags": ["active", "premium"]
}

# Adding multiple examples helps genson refine the schema
builder = SchemaBuilder()
builder.add_object(complex_data)

schema = builder.to_schema()

print("Schema: %s", schema)