from django import template
import os
import os.path

register = template.Library()

@register.filter(name='file_extension')
def file_extension(value):
    """
    Returns the file extension from a file path or URL.
    Example: {{ filename|file_extension }}
    """
    if not value:
        return ""
    
    # Extract filename from the URL or path
    filename = os.path.basename(value)
    
    # Split the filename and get the extension
    _, extension = os.path.splitext(filename)
    
    # Remove the dot and return the extension
    return extension[1:] if extension else "" 