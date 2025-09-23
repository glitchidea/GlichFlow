from django import template

register = template.Library()


@register.filter(name='has_tag')
def has_tag(user, tag_name: str) -> bool:
    """Template filter: {{ user|has_tag:"muhasebeci" }}"""
    try:
        if not hasattr(user, 'tags'):
            return False
        return user.tags.filter(name=tag_name).exists()
    except Exception:
        return False


@register.filter(name='has_any_tag')
def has_any_tag(user, tag_names: str) -> bool:
    """Template filter: {{ user|has_any_tag:"tag1,tag2" }}"""
    try:
        if not hasattr(user, 'tags') or not tag_names:
            return False
        names = [t.strip() for t in str(tag_names).split(',') if t.strip()]
        if not names:
            return False
        return user.tags.filter(name__in=names).exists()
    except Exception:
        return False


