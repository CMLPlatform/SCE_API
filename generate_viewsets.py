import os
import re
import sys

"""Functions to automatically generate Django serializers"""

def parse_models(filepath):
    """Parse filepath and extract class definitions with their fields."""
    classes = {}
    
    with open(filepath, 'r') as f:
        content = f.read()
    lines = content.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i]
        # Find class definitions (no indentation, not commented)
        match = re.match(r'^class\s+(\w+)', line)
        if match:
            class_name = match.group(1)
            fields = []
            abstract = False
            
            # Look ahead for field definitions
            while i+1 < len(lines):
                line = lines[i+1]
                # Stop at end of indentation
                if line and not line[0].isspace():
                    break
                elif line == "        abstract = True":
                    abstract = True
                
                # Match Django model fields (indented lines with = and models.)
                field_match = re.search(r'^\s+(\w+) = (models|CountryField)\.', line)
                if field_match:
                    fields.append(field_match.group(1))
                
                i += 1
            
            if abstract:
                print("Ignoring abstract class", class_name)
            else:
                classes[class_name] = fields
        
        i += 1
    
    return classes

def generate_serializers(classes, output_file):
    """Generate serializer classes."""
    with open(output_file, 'w') as f:
        f.write("from rest_framework import serializers\n")
        f.write("from .models import " + ", ".join(classes.keys()) + "\n\n")
        
        for class_name, fields in classes.items():
            f.write(f"class {class_name}Serializer(serializers.ModelSerializer):\n")
            f.write(f"    class Meta:\n")
            f.write(f"        model = {class_name}\n")
            
            if fields:
                f.write(f"        fields = {fields}\n")
            else:
                f.write(f"        fields = '__all__'\n")
            
            f.write("\n")

def generate_viewsets(classes, output_file):
    """Generate ViewSet classes."""
    with open(output_file, 'w') as f:
        f.write("from rest_framework.viewsets import ModelViewSet\n")
        f.write("from .models import " + ", ".join(classes.keys()) + "\n")
        f.write("from .serializers import " + "Serializer, ".join(classes.keys()) + "\n\n")
        
        for class_name in classes:
            f.write(f"class {class_name}ViewSet(ModelViewSet):\n")
            f.write(f"    queryset = {class_name}.objects.all()\n")
            f.write(f"    serializer_class = {class_name}Serializer\n\n")

def generate_urls(classes, output_file):
    """Generate code to register URLs."""
    with open(output_file, 'w') as f:
        for class_name in classes:
            f.write(f"router.register(r'{class_name.lower()}', views.{class_name}ViewSet, basename='{class_name}')\n")


if __name__ == "__main__":
    # Determine file paths relative to script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    models_file = os.path.join(script_dir, 'mysite/dpp/models.py')
    serial_file = models_file.replace('models.py', 'serializers.txt')
    view_file = models_file.replace('models.py', 'views.txt')
    url_file = models_file.replace('models.py', 'urls.txt')
    
    # Check if models.py exists
    if not os.path.exists(models_file):
        print(f"Error: {models_file} not found")
        sys.exit(1)
    
    classes = parse_models(models_file)
    
    if not classes:
        print("No model classes found in", models_file)
        sys.exit(1)
    
    generate_serializers(classes, serial_file)
    generate_viewsets(classes, view_file)
    generate_urls(classes, url_file)

    print(f"Generated Serializers, ViewSets and URLs for {len(classes)} classes.")

