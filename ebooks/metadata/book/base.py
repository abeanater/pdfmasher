# Copyright 2010, Kovid Goyal <kovid@kovidgoyal.net>
# Copyright 2011 Hardcoded Software (http://www.hardcoded.net)
# 
# This software is licensed under the "GPL v3" License as described in the "LICENSE" file, 
# which should be included with this package. The terms are also available at 
# http://www.hardcoded.net/licenses/gplv3_license

from __future__ import unicode_literals

import copy, traceback

from . import SC_COPYABLE_FIELDS
from . import SC_FIELDS_COPY_NOT_NULL
from . import STANDARD_METADATA_FIELDS
from . import TOP_LEVEL_IDENTIFIERS
from . import ALL_METADATA_FIELDS

NULL_VALUES = {
                'user_metadata': {},
                'cover_data'   : (None, None),
                'tags'         : [],
                'identifiers'  : {},
                'languages'    : [],
                'device_collections': [],
                'author_sort_map': {},
                'authors'      : ['Unknown'],
                'title'        : 'Unknown',
                'user_categories' : {},
                'author_link_map' : {},
                'language'     : 'und'
}


_ = lambda s: s

class Metadata(object):

    '''
    A class representing all the metadata for a book. The various standard metadata
    fields are available as attributes of this object. You can also stick
    arbitrary attributes onto this object.

    Metadata from custom columns should be accessed via the get() method,
    passing in the lookup name for the column, for example: "#mytags".

    Use the :meth:`is_null` method to test if a field is null.

    This object also has functions to format fields into strings.

    The list of standard metadata fields grows with time is in
    :data:`STANDARD_METADATA_FIELDS`.

    Please keep the method based API of this class to a minimum. Every method
    becomes a reserved field name.
    '''

    def __init__(self, title, authors=('Unknown',), other=None):
        '''
        @param title: title or ``_('Unknown')``
        @param authors: List of strings or []
        @param other: None or a metadata object
        '''
        _data = copy.deepcopy(NULL_VALUES)
        object.__setattr__(self, '_data', _data)
        if other is not None:
            self.smart_update(other)
        else:
            if title:
                self.title = title
            if authors:
                # List of strings or []
                self.author = list(authors) if authors else []# Needed for backward compatibility
                self.authors = list(authors) if authors else []

    def is_null(self, field):
        '''
        Return True if the value of field is null in this object.
        'null' means it is unknown or evaluates to False. So a title of
        _('Unknown') is null or a language of 'und' is null.

        Be careful with numeric fields since this will return True for zero as
        well as None.

        Also returns True if the field does not exist.
        '''
        try:
            null_val = NULL_VALUES.get(field, None)
            val = getattr(self, field, None)
            return not val or val == null_val
        except:
            return True

    def __getattribute__(self, field):
        _data = object.__getattribute__(self, '_data')
        if field in TOP_LEVEL_IDENTIFIERS:
            return _data.get('identifiers').get(field, None)
        if field in STANDARD_METADATA_FIELDS:
            return _data.get(field, None)
        try:
            return object.__getattribute__(self, field)
        except AttributeError:
            pass
        if field.startswith('#') and field.endswith('_index'):
            try:
                return self.get_extra(field[:-6])
            except:
                pass
        raise AttributeError(
                'Metadata object has no attribute named: '+ repr(field))

    def __setattr__(self, field, val, extra=None):
        _data = object.__getattribute__(self, '_data')
        if field in TOP_LEVEL_IDENTIFIERS:
            field, val = self._clean_identifier(field, val)
            identifiers = _data['identifiers']
            identifiers.pop(field, None)
            if val:
                identifiers[field] = val
        elif field == 'identifiers':
            if not val:
                val = copy.copy(NULL_VALUES.get('identifiers', None))
            self.set_identifiers(val)
        elif field in STANDARD_METADATA_FIELDS:
            if val is None:
                val = copy.copy(NULL_VALUES.get(field, None))
            _data[field] = val
        elif field in _data['user_metadata'].iterkeys():
            _data['user_metadata'][field]['#value#'] = val
            _data['user_metadata'][field]['#extra#'] = extra
        else:
            # You are allowed to stick arbitrary attributes onto this object as
            # long as they don't conflict with global or user metadata names
            # Don't abuse this privilege
            self.__dict__[field] = val

    def __iter__(self):
        return object.__getattribute__(self, '_data').iterkeys()

    def has_key(self, key):
        return key in object.__getattribute__(self, '_data')

    def deepcopy(self):
        m = Metadata(None)
        m.__dict__ = copy.deepcopy(self.__dict__)
        object.__setattr__(m, '_data', copy.deepcopy(object.__getattribute__(self, '_data')))
        return m

    def deepcopy_metadata(self):
        m = Metadata(None)
        object.__setattr__(m, '_data', copy.deepcopy(object.__getattribute__(self, '_data')))
        return m

    def get(self, field, default=None):
        try:
            return self.__getattribute__(field)
        except AttributeError:
            return default

    def get_extra(self, field, default=None):
        _data = object.__getattribute__(self, '_data')
        if field in _data['user_metadata'].iterkeys():
            try:
                return _data['user_metadata'][field]['#extra#']
            except:
                return default
        raise AttributeError(
                'Metadata object has no attribute named: '+ repr(field))

    def set(self, field, val, extra=None):
        self.__setattr__(field, val, extra)

    def get_identifiers(self):
        '''
        Return a copy of the identifiers dictionary.
        The dict is small, and the penalty for using a reference where a copy is
        needed is large. Also, we don't want any manipulations of the returned
        dict to show up in the book.
        '''
        ans = object.__getattribute__(self,
            '_data')['identifiers']
        if not ans:
            ans = {}
        return copy.deepcopy(ans)

    def _clean_identifier(self, typ, val):
        if typ:
            typ = icu_lower(typ).strip().replace(':', '').replace(',', '')
        if val:
            val = val.strip().replace(',', '|').replace(':', '|')
        return typ, val

    def set_identifiers(self, identifiers):
        '''
        Set all identifiers. Note that if you previously set ISBN, calling
        this method will delete it.
        '''
        cleaned = {}
        for key, val in identifiers.iteritems():
            key, val = self._clean_identifier(key, val)
            if key and val:
                cleaned[key] = val
        object.__getattribute__(self, '_data')['identifiers'] = cleaned

    def set_identifier(self, typ, val):
        'If val is empty, deletes identifier of type typ'
        typ, val = self._clean_identifier(typ, val)
        if not typ:
            return
        identifiers = object.__getattribute__(self,
            '_data')['identifiers']

        identifiers.pop(typ, None)
        if val:
            identifiers[typ] = val

    def has_identifier(self, typ):
        identifiers = object.__getattribute__(self,
            '_data')['identifiers']
        return typ in identifiers

    # field-oriented interface. Intended to be the same as in LibraryDatabase

    def standard_field_keys(self):
        '''
        return a list of all possible keys, even if this book doesn't have them
        '''
        return STANDARD_METADATA_FIELDS

    def custom_field_keys(self):
        '''
        return a list of the custom fields in this book
        '''
        return object.__getattribute__(self, '_data')['user_metadata'].iterkeys()

    def all_field_keys(self):
        '''
        All field keys known by this instance, even if their value is None
        '''
        _data = object.__getattribute__(self, '_data')
        return frozenset(ALL_METADATA_FIELDS.union(_data['user_metadata'].iterkeys()))

    def metadata_for_field(self, key):
        '''
        return metadata describing a standard or custom field.
        '''
        if key not in self.custom_field_keys():
            return self.get_standard_metadata(key, make_copy=False)
        return self.get_user_metadata(key, make_copy=False)

    def all_non_none_fields(self):
        '''
        Return a dictionary containing all non-None metadata fields, including
        the custom ones.
        '''
        result = {}
        _data = object.__getattribute__(self, '_data')
        for attr in STANDARD_METADATA_FIELDS:
            v = _data.get(attr, None)
            if v is not None:
                result[attr] = v
        # separate these because it uses the self.get(), not _data.get()
        for attr in TOP_LEVEL_IDENTIFIERS:
            v = self.get(attr, None)
            if v is not None:
                result[attr] = v
        for attr in _data['user_metadata'].iterkeys():
            v = self.get(attr, None)
            if v is not None:
                result[attr] = v
                if _data['user_metadata'][attr]['datatype'] == 'series':
                    result[attr+'_index'] = _data['user_metadata'][attr]['#extra#']
        return result

    # End of field-oriented interface

    # Extended interfaces. These permit one to get copies of metadata dictionaries, and to
    # get and set custom field metadata

    def get_all_user_metadata(self, make_copy):
        '''
        return a dict containing all the custom field metadata associated with
        the book.
        '''
        _data = object.__getattribute__(self, '_data')
        user_metadata = _data['user_metadata']
        if not make_copy:
            return user_metadata
        res = {}
        for k in user_metadata:
            res[k] = copy.deepcopy(user_metadata[k])
        return res

    def get_user_metadata(self, field, make_copy):
        '''
        return field metadata from the object if it is there. Otherwise return
        None. field is the key name, not the label. Return a copy if requested,
        just in case the user wants to change values in the dict.
        '''
        _data = object.__getattribute__(self, '_data')
        _data = _data['user_metadata']
        if field in _data:
            if make_copy:
                return copy.deepcopy(_data[field])
            return _data[field]
        return None

    def set_all_user_metadata(self, metadata):
        '''
        store custom field metadata into the object. Field is the key name
        not the label
        '''
        if metadata is None:
            traceback.print_stack()
        else:
            for key in metadata:
                self.set_user_metadata(key, metadata[key])

    def set_user_metadata(self, field, metadata):
        '''
        store custom field metadata for one column into the object. Field is
        the key name not the label
        '''
        if field is not None:
            if not field.startswith('#'):
                raise AttributeError(
                        'Custom field name %s must begin with \'#\''%repr(field))
            if metadata is None:
                traceback.print_stack()
                return
            m = {}
            for k in metadata:
                m[k] = copy.copy(metadata[k])
            if '#value#' not in m:
                if m['datatype'] == 'text' and m['is_multiple']:
                    m['#value#'] = []
                else:
                    m['#value#'] = None
            _data = object.__getattribute__(self, '_data')
            _data['user_metadata'][field] = m

    def smart_update(self, other, replace_metadata=False):
        '''
        Merge the information in `other` into self. In case of conflicts, the information
        in `other` takes precedence, unless the information in `other` is NULL.
        '''
        def copy_not_none(dest, src, attr):
            v = getattr(src, attr, None)
            if v not in (None, NULL_VALUES.get(attr, None)):
                setattr(dest, attr, copy.deepcopy(v))

        if other.title and other.title != 'Unknown':
            self.title = other.title
            if hasattr(other, 'title_sort'):
                self.title_sort = other.title_sort

        if other.authors and other.authors[0] != 'Unknown':
            self.authors = list(other.authors)
            if hasattr(other, 'author_sort_map'):
                self.author_sort_map = dict(other.author_sort_map)
            if hasattr(other, 'author_sort'):
                self.author_sort = other.author_sort

        if replace_metadata:
            # SPECIAL_FIELDS = frozenset(['lpath', 'size', 'comments', 'thumbnail'])
            for attr in SC_COPYABLE_FIELDS:
                setattr(self, attr, getattr(other, attr, 1.0 if \
                        attr == 'series_index' else None))
            self.tags = other.tags
            self.cover_data = getattr(other, 'cover_data',
                                      NULL_VALUES['cover_data'])
            self.set_all_user_metadata(other.get_all_user_metadata(make_copy=True))
            for x in SC_FIELDS_COPY_NOT_NULL:
                copy_not_none(self, other, x)
            if callable(getattr(other, 'get_identifiers', None)):
                self.set_identifiers(other.get_identifiers())
            # language is handled below
        else:
            for attr in SC_COPYABLE_FIELDS:
                copy_not_none(self, other, attr)
            for x in SC_FIELDS_COPY_NOT_NULL:
                copy_not_none(self, other, x)

            if other.tags:
                # Case-insensitive but case preserving merging
                lotags = [t.lower() for t in other.tags]
                lstags = [t.lower() for t in self.tags]
                ot, st = map(frozenset, (lotags, lstags))
                for t in st.intersection(ot):
                    sidx = lstags.index(t)
                    oidx = lotags.index(t)
                    self.tags[sidx] = other.tags[oidx]
                self.tags += [t for t in other.tags if t.lower() in ot-st]

            if getattr(other, 'cover_data', False):
                other_cover = other.cover_data[-1]
                self_cover = self.cover_data[-1] if self.cover_data else ''
                if not self_cover: self_cover = ''
                if not other_cover: other_cover = ''
                if len(other_cover) > len(self_cover):
                    self.cover_data = other.cover_data

            if callable(getattr(other, 'custom_field_keys', None)):
                for x in other.custom_field_keys():
                    meta = other.get_user_metadata(x, make_copy=True)
                    if meta is not None:
                        self_tags = self.get(x, [])
                        self.set_user_metadata(x, meta) # get... did the deepcopy
                        other_tags = other.get(x, [])
                        if meta['datatype'] == 'text' and meta['is_multiple']:
                            # Case-insensitive but case preserving merging
                            lotags = [t.lower() for t in other_tags]
                            lstags = [t.lower() for t in self_tags]
                            ot, st = map(frozenset, (lotags, lstags))
                            for t in st.intersection(ot):
                                sidx = lstags.index(t)
                                oidx = lotags.index(t)
                                self_tags[sidx] = other_tags[oidx]
                            self_tags += [t for t in other_tags if t.lower() in ot-st]
                            setattr(self, x, self_tags)

            my_comments = getattr(self, 'comments', '')
            other_comments = getattr(other, 'comments', '')
            if not my_comments:
                my_comments = ''
            if not other_comments:
                other_comments = ''
            if len(other_comments.strip()) > len(my_comments.strip()):
                self.comments = other_comments

            # Copy all the non-none identifiers
            if callable(getattr(other, 'get_identifiers', None)):
                d = self.get_identifiers()
                s = other.get_identifiers()
                d.update([v for v in s.iteritems() if v[1] is not None])
                self.set_identifiers(d)
            else:
                # other structure not Metadata. Copy the top-level identifiers
                for attr in TOP_LEVEL_IDENTIFIERS:
                    copy_not_none(self, other, attr)

        other_lang = getattr(other, 'language', None)
        if other_lang and other_lang.lower() != 'und':
            self.language = other_lang
        if not getattr(self, 'series', None):
            self.series_index = None

    def format_tags(self):
        return ', '.join([unicode(t) for t in self.tags])
        # return u', '.join([unicode(t) for t in sorted(self.tags, key=sort_key)])

    def format_rating(self, v=None, divide_by=1.0):
        if v is None:
            if self.rating is not None:
                return unicode(self.rating/divide_by)
            return 'None'
        return unicode(v/divide_by)

    def format_field(self, key, series_with_index=True):
        '''
        Returns the tuple (display_name, formatted_value)
        '''
        name, val, ign, ign = self.format_field_extended(key, series_with_index)
        return (name, val)

    def __str__(self):
        return self.__unicode__().encode('utf-8')

    def __nonzero__(self):
        return bool(self.title or self.author or self.comments or self.tags)

