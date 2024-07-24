#!/usr/bin/env python3

#
# This script was derived from a previous cleanbm script. The cleanbm
# script stripped out the extraneous HTML attributes like FOLDER,
# ADD_DATE, etc.
# 
# This script has two operating modes:
#
# Mode 1:
#
# With a single input file, the output is a cleaned HTML bookmarks
# file. This means all of the extraneous FOLDER, ADD_DATE,
# etc. attributes have been stripped. Basically, the prmary bookmarks
# is merged against an empty file and /dev/null fills that role.
#
# Mode 2:
#
# Merge two HTML bookmarks file into a single bookmarks file. The
# output will have extraneous content and attributes removed.
#
# I use Safari on my Mac and iPhone. I use Firefox on my Linux Mint
# box. I don't use a shared location, such as iCloud, that all of my
# hosts can use.
#
# The conventions for the two bookmarks files are:
#
# 1. The first specified file is the primary file. The primary file is
#    not the same as a master file, but it can be used for resolving
#    some classes of merging issues.
#
# 2. The second file is the secondary file. It can have entries that
#    aren't present in the primary file. But, there is an attempt to
#    reflect deletions from the primary file in the secondary file.
#
# When an automatic action cannot be determined, an interactive prompt
# will be used for selecting or confirming an action.
#
# Each browser creates HTML bookmarks files containing information
# that makes comparing and merging difficult.
#
# Prior to merging the bookmarks files, the input files are processed
# and modified internally to have a consistent format. At the time of
# writing this comment, the processing involves:
#
# 1. Using the same case for HTML tags and sttributes instead of
#    mixing lowercase and uppercase.
#
# 2. Removing the Safari FOLDED attribute from headers corresponding
#    to folders.
#
# 3. For anchor tags, only retaining the HREF attribute and removing
#    all of the other attributes. This will remove the known Firefox
#    ADD_DATE, LAST_MODIFIED, ICON_URI, and ICON attributes.
#
# In addition to removing extraneous attributes, the processing
# attempts to consistently handle entityrefs and charrefs
# consistently. Safari does not appear to use charrefs, e.g. &#39; for
# ' while Firefox does. Also, Safari and Firefox don't handle entities
# the same. See below for more details.
#

import pdb

from abc import ABC, abstractmethod
import argparse
from collections import deque
from enum import Enum, auto
import html
from html.parser import HTMLParser
import io
#from itertools import zip_longest
#from itertools import *
import os
import re
import sys

#
# :TODO: Learn to use type annotations and add them.
#
# :TODO: Should I ensure encoding='utf-8' is used? How do I determine
# the encoding without looking for an HTML tag containing the
# encoding?  Or, does the HTML module automatically detect and use the
# proper encoding as it processes the HTML? Maybe this is already
# using UTF-8 encoding.
#
# :TODO: Do I need to special case Bookmarks title vs. folder? What
# about Bookmarks Menu? Need to see what Safari specific and Firefox
# specific folders need special handling.
#
# :TODO: Determine how to handle non-bookmarks files when allowed, but
# contain unxpected elements. Maybe eliminate --no-bookmarks.
#

#
# The global instance of a Log class for sending the debugging output.
#
log = None

#
# Debugging verbosity level. It is only meaningful when greater than
# 0.
#
debug_level = 0

#
# Debugging and logging support.
#
def debugging(level=0):
    global debug_level
    return debug_level > 0 and debug_level >= level

def debugmsg(level, file, format, *args):
    if debugging(level):
        print(f'DBG_{level} ' + format.format(*args), end='', file=file)

def warnmsg(format, *args, file=sys.stderr):
    print(f'WARNING ' + format.format(*args), end='', file=file)

#
# Utility functions.
#

#
# Since assert() is a no-op when __debug__ is false, custom assertion
# checks are provuded that are always available.
#
def fail_when(expr, message, where=None):
    """Raise an AssertionError exception when expr is True.

    Arguments:
    expr - an expression to evaluate for a boolean result.
    message - an informational message for the exception.
    
    Optional keyword arguments:
    where - the location of the data causing the failure.

    The exception will contain the location of the failure in the
    script. When there are multiple data sources, for example input
    files, it can be useful to include which data source caused the
    failure.
    """

    if expr:
        if where:
            raise AssertionError(message + ' in ' + where)
        else:
            raise AssertionError(message)

def fail_always(message, where=None):
    """Always raise an AssertionError exception.
    
    Arguments:
    message - an informational message for the exception.
    
    Optional keyword arguments:
    where - the location of the data causing the failure.

    See fail_when() for the purpose of the where parameter.
    """

    fail_when(True, message, where=where)

def unimplemented(s):
    """Raise an exception for features and support that are not implemented.

    Arguments:
    s - a message about what is unimplemented.

    When portions of an implementation are absent. Some use cases are:

    An overridable method in a class does not implement the necessary
    support and should fail if something triggers invoking the method.

    When an Enum has new values added, a check can be used in
    functions and methods that need to be updated when encountering
    the new enumerated value.

    :NOTE: When an enumerated value is incorrect for some usage, use
    fail_when() and not unimplemented().
    """

    raise NotImplementedError(s + ' is unimplemented')

def make_path(path_list):
    """Create and return a / starting and separated path from a list.

    Keyword arguments:
    path_list - the list of components of the path.

    The empty string, '', always starts the path, so the implicit
    first character in the string is '/'.
    """

    dirs = list(path_list)

    if len(dirs) == 0:
        path = '/'
    else:
        path = '/'.join([''] + dirs)

    return path

def full_path(parent, folder):
    """Return a '/' separated path of a parent path and a folder name.
    
    Keyword arguments:
    parent - a '/' separated path of the parent of the folder.
    folder - the name of the folder.

    The empty string, '', is also the implicit first component of the
    path.
    """

    if parent == '/':
        parent = ''

    path = '{}/{}'.format(parent, folder)

    return path

def make_whitespace(mode, depth):
    """Return a whitespace sequence for indenting an HTML element.
    
    Keyword arguments:
    mode - the style of a single whitespace chunk.
    depth - the number of whitespace chunks to generate.

    For SPACE mode, a chunk is 4 spaces wide.
    For TAB mode, a chunk is a hard TAB.
    """

    #
    # macOS Ventura (13.6) has Python 3.9.
    # Python 3.10+ supports match.
    #
    if mode == IndentationMode.SPACE:
        ws = ' ' * (4 * depth)
    elif mode == IndentationMode.TAB:
        ws = '\t' * depth
    else:
        unimplemented(str(mode))

    return ws

def short_source(source):
    """Return a single letter abbreviation for a Source value."""
    if source == Source.PRIMARY:
        tag = 'p'
    elif source == Source.SECONDARY:
        tag =  's'
    elif source == Source.BOTH:
        tag = 'b'
    else:
        unimplemented(str(source))

    return tag

def short_state(state):
    """Return a single letter abbreviation for an ElementState."""
    if state == ElementState.SAVED:
        tag = 's'
    elif state == ElementState.HANDLED:
        tag =  'h'
    elif state == ElementState.DELETED:
        tag = 'd'
    else:
        unimplemented(str(state))

    return tag

#
# Support and helper classes.
#

class Log:
    """A wrapper class holding a handle for directing output.

    The primary purposes is for instantiating a global instance to use
    as the file keyword argument to functions such as print().

    Public methods:
    target - getter.
    target(file object) - setter.
    """

    def __init__(self, log_target):
        """Create an instance to hold the log_target handle."""
        self._target = log_target

    @property
    def target(self):
        return self._target

    @target.setter
    def target(self, log_target):
        self._target = log_target

class FileHandle:
    """A wrapper class for turning OSError exceptions into error strings.

    Only functions where an an error string is to be available are
    wrapped.

    Public methods:
    handle - getter.
    error - getter.

    open - open a file and store the handle for I/O. Set _error on
           failure.
    """

    def __init__(self):
        """Construct a FileHandle instance."""
        self._handle = None
        self._error = None

    @property
    def handle(self):
        return self._handle

    @property
    def error(self):
        return self._error

    def open(self, file, mode='r'):
        """Open file setting the internal _handle on success.

        If there is a failure, _handle remains unset and _error is
        set to an error string.

        Keyword arguments:
        file - the name of the file to open.
        mode - optional mode for opening the file.
        
        Nothing is returned.
        """

        try:
            self._handle = open(file, mode=mode)
        except OSError as os_error:
            self._error = os_error

class IndentationMode(Enum):
    """The supported whitespace indentation styles."""
    TAB = auto()
    SPACE = auto()

class BookmarkElement(Enum):
    """The HTML element types for a bookmark element."""
    FOLDER = auto()
    ANCHOR = auto()

class BookmarksStyle(Enum):
    """The heuristically determined style of an HTML bookmarks file.

    Look for the presence of contents that are specific to a
    particular version of an HTML bookmarks file. This information is
    not currently used. One use would be for the syle of HTML to
    generate.

    :TODO: It may be best to include an undetermined value for better
    support of files that are neither format or are a mixture of
    styles. Then again, removing this entire notion of style may be
    the best choice.
    """

    SAFARI = auto()
    FIREFOX = auto()

class Source(Enum):
    """The input file containing an Element."""
    PRIMARY = auto()
    SECONDARY = auto()
    BOTH = auto()

class ElementState(Enum):
    """The state of an Element during processing.

    Values:
    SAVED - the Element has been saved in tracking data structures.
    HANDLED - the Element has been handled and needs no further
              processing.
    DELETED - the Element has been deleted.

    When iterating an iterable, an Element can not be removed. So, a
    DELETED state is used instead.
    """

    SAVED = auto()
    HANDLED = auto()
    DELETED = auto()

class Element(ABC):
    """An abstract base class for HTML bookmark elements.

    State that is common to all Elements is stored in this
    class. Public accessor ahd predicate methods are implement in this
    class. Abstract methods that must be implemented in a derived
    class are defined.

    Public methods:
    source - getter.
    source(Source) - setter.
    parent_path - getter.
    nesting_depth - getter.
    state - getter.
    state(ElementState) - setter.
    dont_ask - getter
    dont_ask(bool) - setter.
    is_saved - predicate.
    is_handled - predicate.
    is_deleted - predicate.
    is_folder - predicate.
    is_anchor - predicate.

    Abstract methods:
    type - the kind of BookmarkElement.
    name - the string name of the Element.
    make_path_key - the Element key for the by_path dictionaries.
    element_str - the string version of the Element in HTML format.
    pretty_str - a more readable string with some Element attributes.
    verbose_str - a more readable and verbose string containing
                  Element attributes.
    __eq__ - equal operator.
    __ne__ - not equal operator.
    __str__ - str() representation with more attributes than
             verbose_str()
    """

    global log

    def __init__(self, source, parent_path, nesting_depth):
        """Assign the common attributes of an Element.

        Keyword arguments:
        source - the Source containing the Element (mutable).
        parent_path - the '/' separated path of the parent folder. The
                      path is absolute and starts with '/'
                      (immutable).
        nesting_depth - the depth of the Element in logical tree
                        described by an HTML bookmarks file
                        (immutable).

        The initial ElementState is set to SAVED.
        """

        self._source = source
        self._parent_path = parent_path
        self._nesting_depth = nesting_depth
        self._state = ElementState.SAVED
        self._dont_ask = False

    @property
    def source(self):
        return self._source

    @source.setter
    def source(self, source):
        self._source = source

    @property
    def parent_path(self):
        return self._parent_path

    @property
    def nesting_depth(self):
        return self._nesting_depth

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, state):
        self._state = state

    @property
    def dont_ask(self):
        return self._dont_ask

    @dont_ask.setter
    def dont_ask(self, dont_ask):
        self._dont_ask = dont_ask

    def is_saved(self):
        return self._state == ElementState.SAVED

    def is_handled(self):
        return self._state == ElementState.HANDLED

    def is_deleted(self):
        return self._state == ElementState.DELETED

    def is_folder(self):
        return self.type == BookmarkElement.FOLDER

    def is_anchor(self):
        return self.type == BookmarkElement.ANCHOR

    @property
    @abstractmethod
    def type(self):
        pass

    @property
    @abstractmethod
    def name(self):
        pass

    @abstractmethod
    def make_path_key(self):
        pass

    @abstractmethod
    def element_str(self):
        pass

    @abstractmethod
    def pretty_str(self):
        pass

    @abstractmethod
    def verbose_str(self):
        """Display a verbose version of an Element.

        This explicit method exists so that __repr__() is available
        for future use.
        """
        pass

    @abstractmethod
    def __eq__(self):
        pass

    @abstractmethod
    def __ne__(self):
        pass

    @abstractmethod
    def __str__(self):
        pass

class Folder(Element):
    """A folder bookmark Element derived from the Element base class.

    Public methods:
    folder - getter.
    id - getter.

    See the documentation for the Element base class for descriptions
    of the other methods.
    """

    global log

    def __init__(self, source, nesting_depth, parent_path, folder, id=None):
        """Construct a Folder element.

        Subclass keyword arguments:
        folder - the name of the Folder element (immutable).
        id - optionally present "id" attribute (immmutable).

        The other keyword arguments are passed to the Element base
        class constructor.
        """

        self._folder = folder
        self._id = id

        super().__init__(source=source,
                         parent_path=parent_path,
                         nesting_depth=nesting_depth)

    @property
    def folder(self):
        return self._folder

    @property
    def id(self):
        return self._id

    @property
    def type(self):
        return BookmarkElement.FOLDER

    @property
    def name(self):
        return self._folder

    def make_path_key(self):
        #
        # The full path for a folder is unique.
        #
        return full_path(parent=self.parent_path,
                         folder=self.folder)

    def element_str(self):
        id = ''
        if self._id != None:
            id = f' id="{self.id}"'
        return '<H3{}>{}</H3>'.format(id, self.folder)

    def pretty_str(self):
        return '{}:'.format(self.folder)

    def verbose_str(self):
        pretty = self.pretty_str()
        return 'd {} s {} st {} {}'.format(self.nesting_depth,
                                           self.source.name,
                                           self.state.name,
                                           pretty)

    def __eq__(self, other):
        return (other and self.parent_path == other.parent_path and
                self.folder == other.folder)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return 'Folder(d {} s {} st {} p "{}" f "{}")'.format(
            self.nesting_depth,
            self.source.name,
            self.state.name,
            self.parent_path,
            self.folder)

class Anchor(Element):
    """An anchor bookmark Element derived from the Element base class.

    An Anchor element contains an href for a URI and optional anchor
    text.

    Public methods:
    href - getter
    anchor_text - getter

    See the documentation for the Element base class for descriptions
    of the other methods.
    """

    global log

    def __init__(self,
                 source,
                 nesting_depth,
                 parent_path,
                 href,
                 anchor_text):
        """Construct an Anchor element.

        Subclass keyword arguments:
        href - the URI which is usually a http/https URL (immutable).
        anchor_text - the descriptive text of the anchor (immutable).

        The other keyword arguments are passed to the Element base
        class constructor.
        """

        self._href = href
        self._anchor_text = anchor_text

        super().__init__(source=source,
                         parent_path=parent_path,
                         nesting_depth=nesting_depth)

    @property
    def href(self):
        return self._href

    @property
    def anchor_text(self):
        return self._anchor_text

    @property
    def type(self):
        return BookmarkElement.ANCHOR

    @property
    def name(self):
        """Use the href as the name of the Anchor element."""
        return self._href
    
    def make_path_key(self):
        """Return a key for accessing a by_path dictionary.

        Use the parent_path and href since the anchor will be in a
        folder. However, a href with or without differing anchor text
        can be present multiple times in the same folder. Use '@@' as
        a separator since it's more readable than '/'.
        """

        return self.parent_path + '@@' + self.href

    def element_str(self):
        return '<A HREF="{}">{}</A>'.format(self.href, self.anchor_text)

    def pretty_str(self):
        return '<{}> {}'.format(self.href, self.anchor_text)

    def verbose_str(self):
        pretty = self.pretty_str()
        return 'd {} s {} st {} {}'.format(self.nesting_depth,
                                           self.source.name,
                                           self.state.name,
                                           pretty)

    def __eq__(self, other):
        """Compare 2 Anchor elements for equality.

        The anchor text is not considered for equality. The anchor
        text is merely descriptive and can be anything for identical
        hrefs at the same parent path, aka folder.
        """

        return (other and self.parent_path == other.parent_path and
                self.href == other.href)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return 'Anchor(d {} s {} st {} p "{}" h "{}" a "{}")'.format(
            self.nesting_depth,
            self.source.name,
            self.state.name,
            self.parent_path,
            self.href,
            self.anchor_text)

class Node:
    """A node for an item in an ElementTree.

    Currently, all items are bookmark Elements.

    Public data members:
    item - the Element stored in the Node.
    children - the array of child Nodes in a Folder item.
    """

    global log

    def __init__(self, item):
        """Construct a Node holding the Element as the item member."""
        self.item = item
        self.children = []

    def __str__(self):
        """A string representation of a node.

        The number of children is included, but child nodes are
        omitted for brevity.
        """

        return 'Node({} [{}])'.format(self.item, len(self.children))

def NoneNode():
    """Create and return a Node using None for the item's value."""
    return Node(item=None)

class ElementTree:
    """A tree represention of an HTML bookmarks file.

    An HTML bookmarks file has 2 Element types for representing
    bookmarks:

    folder - a container of bookmark Elements.
    anchor - a specific URI for a bookmark.

    An ElementTree is a tree of Node objects where the item in a Node
    is a bookmark Element.

    Folders are similar to directories in a file system. Using a
    synthetic root folder, named '/', holding the top-level Elements,
    a tree can be used to represent the bookmark Elements. When a
    <dl>, description list, is encountered, a new list of <dt>,
    description term, tags may follow. Preceding the <dl> tag will be
    a <dt> tag for the name of the folder associated with the new <dl>
    list. A <dl> list may be empty, i.e. <dl></dl>

    The merging of 2 bookmark files can be performed by merging 2
    ElementTrees.

    :NOTE: Currently, there is no support for:

    update - modifying an item in the tree.
    lookup - find an item in the tree.

    In addition, there is no support for inserting an item at a
    specific location, after a specific item, or before a specific
    item in a folder.

    Public methods:
    insert - insert an Element into the ElementTree.
    print_bookmarks - generate and print HTML formatted bookmarks.

    Public debugging methods:
    debug_dump - display the items in the ElementTree.
    debug_dump_with_tags - display the items in the ElementTree with
                           HTML tags.
    """

    global log

    def __init__(self, item):
        """Construct a tree with item in the root Node."""
        self.root = Node(item=item)

    def insert(self,
               element,
               path_list,
               root=None,
               nesting_depth=0):
        """Insert an element into the Element tree using recursion.

        Keyword arguments:
        element - the Element instance to be inserted.
        path_list - the list of the names of the parent folders.
        root - an optional root of an Element tree where an Element
               should be inserted.
        nesting_depth - the optional nesting depth of the insertion
                        for this call.

        When root == None, the root of this Element tree is
        implied. Otherwise, root is the root of a subtree where an
        Element should be inserted.

        The implicit '/' root folder is at nesting_depth == 0. Each
        folder increases the nesting depth by 1 when descending into
        the folder.

        Currently, insertion is idempotent. If an Element is already
        present, the Node and the item, i.e. Element, is not modified.

        :NOTE: This method is implemented assuming that the folder
        structure of a bookmarks file incrementally adds new folders and
        anchors such that all of the parents of the Element have already
        been inserted. In other words:
        
        A folder, c, with the path /a/b/c will not be inserted when
        only /a is in the tree. If this situation arises, then a
        missing folder Element will need to be created and inserted
        here before proceeding.
        """

        if root == None:
            root = self.root

        debugmsg(2,
                 log.target,
                 '  {} tree update element {} root {} path_list {}\n',
                 nesting_depth,
                 element,
                 root,
                 path_list)

        if len(path_list) == 0:
            debugmsg(1,
                     log.target,
                     '  {} tree update insert@1 element {} in {}\n',
                     nesting_depth,
                     element,
                     root)
            root.children.extend([Node(item=element)])
            return

        name = path_list.popleft()
        for node in iter(root.children):
            item = node.item
            debugmsg(2,
                     log.target,
                     ('  {} tree update check name {} against ' +
                      'item {} path_list {}\n'),
                     nesting_depth,
                     name,
                     item,
                     path_list)
            if item.is_folder() and item.folder == name:
                self.insert(element=element,
                            path_list=path_list,
                            root=node,
                            nesting_depth=nesting_depth+1)
                return

        debugmsg(1,
                 log.target,
                 ('  {} tree update insert@2 element {} in {} ' +
                  'path_list {}\n'),
                 nesting_depth,
                 element,
                 root,
                 path_list)
        root.children.extend([Node(item=element)])

    def print_bookmarks(self, style, output, root=None):
        """Generate and print the HTML bookmarks from the ElementTree."""

        fail_when(style != BookmarksStyle.FIREFOX,
                  f'only {BookmarksStyle.FIREFOX.name} style is supported')

        if root == None:
            root = self.root

        expected_depth = None
        for node in iter(root.children):
            element = node.item
            if expected_depth == None:
                expected_depth = element.nesting_depth

            #
            # All elements in the children must be at the same
            # nesting_depth. Originally, this caught situations where
            # folder names containing '/' were mishandled since the
            # '/' would be treated as a path component separator.
            #
            fail_when(expected_depth != element.nesting_depth,
                      'depth {} != depth {} for {}'.format(
                          expected_depth,
                          element.nesting_depth,
                          element))

            #
            # Add 1 to the depth since there is a top-level <dl>.
            #
            depth = element.nesting_depth + 1
            ws = make_whitespace(mode=IndentationMode.SPACE,
                                 depth=depth)

            if element.is_folder():
                id = ''
                if element.id != None:
                    id = f' id="{element.id}"'

                print('{}<DT><H3{}>{}</H3>'.format(ws, id, element.folder),
                      file=output)

                print('{}<DL><p>'.format(ws), file=output)

                self.print_bookmarks(style=style,
                                     output=output,
                                     root=node)

                print('{}</DL><p>'.format(ws), file=output)

            elif element.is_anchor():
                print('{}<DT><A HREF="{}">{}</A>'.format(
                    ws,
                    element.href,
                    element.anchor_text),
                      file=output)
            else:
                unimplemented(str(element))

    def debug_dump(self,
                   label=None,
                   root=None,
                   show_deleted=True):
        """Display the elements in the ElementTree.

        This method is a no-op when the debug_level == 0.

        label - an optional label to display in a header.
        root - an optional root node of an Element tree.
        show_deleted - when True, display Elements with state DELETED.
        """

        if not debugging():
            return

        if root == None:
            root = self.root

        if label != None:
            header = '-' * 10
            header += f' {label} '
            header += '-' * 10
            print(header, file=log.target)

        #
        # :NOTE: Currently, there will be no deleted Elements prior to
        # handling duplicates.
        #
        for node in iter(root.children):
            element = node.item

            if not show_deleted and element.is_deleted():
                continue

            source_tag = short_source(source=element.source)
            state_tag = short_state(state=element.state)
            ws = make_whitespace(mode=IndentationMode.SPACE,
                                 depth=element.nesting_depth)
            out = element.pretty_str()
            print('{:> 4} {} {} {}{}'.format(element.nesting_depth,
                                             source_tag,
                                             state_tag,
                                             ws,
                                             out),
                  file=log.target)

            if element.is_folder():
                self.debug_dump(root=node, show_deleted=show_deleted)

    def debug_dump_with_tags(self,
                             label=None,
                             root=None,
                             show_deleted=False):
        """Display the Elements in the Element tree as HTML tags.

        This method is a no-op when the debug_level == 0.

        The documentation for debug_dump() describes the behavior for
        this method too, but the following differences here are:

        show_deleted - defaults to False here.

        The Element is displayed as a <dt> tag indented with
        whitespace according to the nesting_depth.
        """

        if not debugging():
            return

        if root == None:
            root = self.root

        if label != None:
            header = '-' * 10
            header += f' {label} '
            header += '-' * 10
            print(header, file=log.target)

        #
        # <dl> tags are omitted.
        #
        #
        # :NOTE: Currently, there will be no deleted Elements prior to
        # handling duplicates.
        #
        for node in iter(root.children):
            element = node.item

            if not show_deleted and element.is_deleted():
                continue

            ws = make_whitespace(mode=IndentationMode.SPACE,
                                 depth=element.nesting_depth)

            out_element = element.element_str()
	    #
	    # Include the <DT> tag for easier diffing against the <DT>
	    # tags extracted from an input file and this merged
	    # output.
	    #
            print('{}<DT>{}'.format(ws, out_element),
                  file=log.target)

            if element.is_folder():
                self.debug_dump_with_tags(root=node,
                                          show_deleted=show_deleted)

class ByPathItem:
    """Provide support for duplicate Elements with the same key.

    For dictionaries using a path as the key, encapsulate that there
    can be duplicates at the same path (key).

    There cannot be duplicate folders.

    All duplicates will be anchors with the same href since the anchor
    text is disregarded.

    Elements are inserted into a list according to their Source. When
    an Element will move to the BOTH list, it is removed from its
    original list.
    """

    global log

    def __init__(self):
        """A by_path dictionary entry starts with empty lists."""
        self._element_lists = {
            Source.PRIMARY:[],
            Source.SECONDARY:[],
            Source.BOTH:[],
        }

    @property
    def element_lists(self):
        """Return the dictionary for all list by the Source."""
        return self._element_lists

    def element_list(self, source):
        """Return the list corresponding to a specific Source."""
        return self._element_lists[source]


#
# A collection of bookmark Elements. A bookmark Element is either a
# folder or an anchor with a href.
#
class Bookmarks:
    """An encapsulation of the data and state of an HTML bookmarks file.

    A bookmarks input file is parsed using an HTMLParser subclass. The
    results of the parsing will populate data members within an instance
    of the Bookmarks class.

    After an input file is parsed, the _by_path dictionary and the
    _element_tree are used for future processing such as merging.

    Public methods:
    file - getter
    source - getter
    text - getter
    text(string) - setter
    ordered_elements - getter
    element_tree - getter
    num_unique - getter
    by_path - getter

    add_anchor - add an Anchor instance to the internal containers.
    update_elements - update the internal containers.
    verify_handled - verify that all Elements have been handled in
                     some form.

    Public debugging methods:
    debug_dump_by_path - dump the contents of the by_path dictionary.
    debug_dump_ordered_elements - dump the Elements in the order
                                  encountered in an input file.
    debug_dump_indented - dump the Elements in the order encountered
                          in an input file with nesting_depth amount
                          of indentation.
    debug_dump_duplicates - dump all of the Elements where there is
                            one or more instances of the same Element.

    Private methods:
    _update_ordered_elements - update the ordered list of Elements.
    """

    global log

    def __init__(self, file, source, by_path, num_unique):
        """Construct a Bookmarks instance.

        Keyword arguments:
        file - the name of the HTML bookmarks input file (immutable).
        source - the Source value of the input (immutable).
        by_path - an initial dictionary for initializing the by_path
                  member in this Bookmarks instance.
        num_unique - the number of unique Elements encountered. When
                     not 0, this is the number of Elements from the
                     PRIMARY argument.
        
        The Source will be PRIMARY or SECONDARY.
        """

        self._file = file
        self._source = source

        #
        # This will hold the parsed and cleaned HTML text after
        # parsing the input file. Currently, this is only used for
        # debugging.
        #
        self._text = None

        #
        # A dictionary of the Elements with the key being the path of
        # the Element. The Entries are dictionaries containing one or
        # more Elements for the PRIMARY, SECONDARY, and BOTH Source
        # values. Duplicate Elements will have multiple occurences in
        # the lists. Only Anchors can have duplicates.
        #
        # In the secondary bookmarks, this dictionary holds Elements
        # from both files.
        #
        self._by_path = by_path | dict()

        #
        # This only contains the Elements from the input file for this
        # Source, PRIMARY or SECONDARY, in the same order as the
        # source file. Every Element from the input file will be in
        # this list, so this list is used for verifying that all of
        # the Elements have been handled in some form.
        #
        self._ordered_elements = []

        #
        # THe top-level bookmark items, folders and anchors, are
        # within an implicit "/" root folder. Since the top-level
        # items are at nesting_depth 0, the "/" is at depth -1. The
        # implicit root really should not be named "/", but that's the
        # most convenient with a parent_path of ''.
        #
        self._element_tree = ElementTree(item=Folder(source=source,
                                                     nesting_depth=-1,
                                                     parent_path='',
                                                     folder='/'))

        #
        # The number of unique Elements encountered across the input
        # files process so far. For the SECONDARY Source, this will
        # start as the number of Elements in the PRIMARY Source. When
        # processing the SECONDARY Source, Elements only in the
        # SECONDARY source will be counted. Currently, this is only
        # used as a debugging aid.
        #
        self._num_unique = num_unique

    @property
    def file(self):
        return self._file

    @property
    def source(self):
        return self._source

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, text):
        self._text = text

    @property
    def ordered_elements(self):
        return self._ordered_elements

    @property
    def element_tree(self):
        return self._element_tree

    @property
    def num_unique(self):
        return self._num_unique

    @property
    def by_path(self):
        return self._by_path

    def add_anchor(self,
                   source,
                   nesting_depth,
                   parent_path,
                   href,
                   anchor_text):
        """Add an Anchor element to all of the internal containers.

        Keyword arguments:
        source - the Source value of the input.
        nesting_depth - the depth in the <dl> tree hierarchy.
        parent_path - the '/' separated path of the parent folder. The
                      path is absolute and starts with '/'.
        href - the URI of the <a> element.
        anchor_text - the optional descriptive text of the <a> URI.
        """

        element = Anchor(source=source,
                         nesting_depth=nesting_depth,
                         parent_path=parent_path,
                         href=href,
                         anchor_text=anchor_text)

        self.update_elements(element=element)

    def update_elements(self, element):
        """Add an Element to all of the internal containers.

        - Add an Element to the by_path dictionary.
        - If an Element is found in the other Source, then move it
          from the list for the other Source in the by_path entry to
          the BOTH list.
        - Add the Element to the _ordered_elements for this Bookmarks
          instance.
        - Insert the Element into the ElementTree for this Bookmarks
        instance.
        """

        type = element.type
        is_anchor = element.is_anchor()

        #
        # macOS Ventura (13.6) has Python 3.9.
        # Python 3.10+ supports match.
        #
        if (type != BookmarkElement.FOLDER and
            type != BookmarkElement.ANCHOR):
            raise unimplemented(str(type))

        source = element.source
        if source == Source.SECONDARY:
            other_source = Source.PRIMARY
        else:
            other_source = Source.SECONDARY

        key = element.make_path_key()

        #
        # Handle anchors that are duplicated in the same folder. This
        # can be any anchor, but often it will be about:blank used as
        # a separator with or without different anchor texts.
        #
        by_path = self.by_path
        if key not in by_path:
            by_path[key] = ByPathItem()

        element_list = by_path[key].element_list(source=source)
        other_element_list = by_path[key].element_list(source=other_source)
        debugmsg(1,
                 log.target,
                 '  by_path look for {} in {} list length {} at "{}"\n',
                 element,
                 other_source.name,
                 len(other_element_list),
                 key)

        #
        # Look for elements in other inputr source. For now, this is
        # only interesting when this element is from the SECONDARY
        # input and the other source is the PRIMARY input. Since list
        # members cannot be removed or inserted while iterating, a new
        # list is created for replacing a list in the by_path entry.
        #
        changed_element = None
        action = None
        n_modified = 0
        both_list = by_path[key].element_list(source=Source.BOTH)
        new_other_list = []

        for a_elem in other_element_list:
            eq_elem = a_elem == element
            eq_anchor_text = False
            if is_anchor and a_elem.anchor_text == element.anchor_text:
                eq_anchor_text = True

            debugmsg(2,
                     log.target,
                     ('  by_path a_elem {} equal {} ' +
                      'anchor_text equal {} element {}\n'),
                     a_elem,
                     eq_elem,
                     eq_anchor_text,
                     element)

            #
            # When the sources differ and the element types are the
            # same
            #
            #   If folders are equal, move into the BOTH list, or
            #
            #   If an anchor and its anchor text are equal, move it
            #   into the BOTH list.
            #
            # Otherwise, place the element into the list for this
            # source. Any modifications will modify all equal
            # elements.
            #
            # Since the elements moved to the BOTH list are identical,
            # changed_element will be the first element moved to the
            # BOTH list.
            #
            if a_elem.type == type and a_elem == element:
                fail_when(a_elem.source == element.source,
                          'incorrect a_elem source ' + a_elem.source.name)
                          
                if eq_anchor_text:
                    changed_element = a_elem if changed_element == None\
                        else changed_element
                    action = 'MODIFY'
                    a_elem.source = Source.BOTH
                    both_list.extend([a_elem])
                    n_modified += 1
                elif not is_anchor:
                    changed_element = a_elem if changed_element == None\
                        else changed_element
                    action = 'MODIFY'
                    a_elem.source = Source.BOTH
                    both_list.extend([a_elem])
                    n_modified += 1
                else:
                    new_other_list.extend([a_elem])
            else:
                new_other_list.extend([a_elem])

        if n_modified > 0:
            by_path[key].element_lists[other_source] = new_other_list

        if changed_element == None:
            changed_element = element
            action = 'INSERT'
            element_list.extend([element])

        debugmsg(1,
                 log.target,
                 ('  by_path {} modified {} length {} ' +
                  ' other length {} element {} at {}\n'),
                 action,
                 n_modified,
                 len(element_list),
                 len(other_element_list),
                 changed_element,
                 key)

        #
        # For MODIFY of multiple elements above, changed_element will
        # be the first one modified.
        #
        self._update_ordered_elements(element=changed_element)

        path_list = deque(changed_element.parent_path.split(sep='/'))
        path_list.popleft()
        self.element_tree.insert(element=changed_element,
                                 path_list=path_list)

    def _update_ordered_elements(self, element):
        """Append an Element to the list of ordered Elements.

        Keyword arguments:
        element - the Element instance to be appended.

        The Element is always appended to the list. The num_unique
        counter is incremented when the Source is not BOTH.
        """

        type = element.type
        if (type != BookmarkElement.FOLDER and
            type != BookmarkElement.ANCHOR):
            raise unimplemented(str(type))
    
        self.ordered_elements.extend([element])
        if element.source != Source.BOTH:
            self._num_unique += 1

        debugmsg(1, log.target, '  append {}\n', element)

    def verify_handled(self):
        """Verify that no Element is in the SAVED state.

        Iterate over the ordered list of Elements. Count how many
        Elements are in the SAVED state. The ElementStates HANDLED and
        DELETED are both treated as handled.
        """

        unhandled = 0
        for element in iter(self.ordered_elements):
            if element.is_saved():
                warnmsg('unhandled {}\n', element)
                key = element.make_path_key()
                for source in Source:
                    element_list = self.by_path[key].element_list(
                        source=source)
                    count = len(element_list)
                    list_strs = [str(x) for x in element_list]
                    warnmsg('  {} elements in by_path list {}\n',
                            count,
                            list_strs)
                    unhandled += 1

        #
        # Unhandled elements are fatal when not debugging.
        #
        if not debugging():
            fail_when(unhandled > 0, f'{unhandled} elements unhandled')

    def debug_dump_by_path(self, label):
        """Display the Elements in the by_path dictionary.

        This method is a no-op when the debug_level == 0.

        Keyword arguments:
        label - the text to place in the header before display the
                Elements.

        Each entry will have a dictionary. The dictionary is keyed by
        the Source value: PRIMARY, SECONDARY, and BOTH. Each list may
        contain more than one element. For example, there are 2
        elements that are Anchors. Each has the same full path and
        href. Both will be in the entry lists.
        """

        if not debugging():
            return

        header = '-' * 10
        header += f' {label} '
        header += '-' * 10
        print(header, file=log.target)

        #
        # :NOTE: Deleted elements are dumped for debugging and
        # informational purposes. Currently, there will be no deleted
        # elements prior to handling duplicates.
        #
        by_path = self.by_path
        for key in iter(by_path):
            for source in Source:
                element_list = by_path[key].element_list(source=source)
                print('{} key {} list length {}'.format(source.name,
                                                        key,
                                                        len(element_list)),
                      file=log.target)

                length = len(element_list)
                for element in iter(element_list):
                    if element == None:
                        continue
                    type = element.type
                    if (type != BookmarkElement.FOLDER and
                        type != BookmarkElement.ANCHOR):
                        raise unimplemented(str(type))

                    print('  {} {}'.format(source.name,
                                           element),
                          file=log.target)

                    length -= 1
                    fail_when(element.is_folder() and length > 0,
                              ('unexpected duplicate folder ' +
                               element.pretty_str()))

    def debug_dump_ordered_elements(self, label):
        """Display the Elements in the ordered list of Elements.

        This method is a no-op when the debug_level == 0.

        Keyword arguments:
        label - the text to place in the header before display the
                Elements.
        """

        if not debugging():
            return

        header = '-' * 10
        header += f' {label} '
        header += '-' * 10
        print(header, file=log.target)

        #
        # :NOTE: Deleted elements are dumped for debugging and
        # informational purposes. Currently, there will be no deleted
        # elements prior to handling duplicates.
        #
        elements = self.ordered_elements
        for element in iter(elements):
            type = element.type
            if (type != BookmarkElement.FOLDER and
                type != BookmarkElement.ANCHOR):
                raise unimplemented(str(type))

            print('{}'.format(element), file=log.target)

    #
    #
    def debug_dump_indented(self, label, verbose=False):
        """Display versions of Elements with their indentation.

        This method is a no-op when the debug_level == 0.

        Keyword arguments:
        label - the text to place in the header before display the
                Elements.
        verbose - display a pretty or verbose version of an Element.

        Iterate over the ordered list of Elements for this Bookmarks
        instance. For each Element, display a represenation indented
        according to the nesting_depth of the Element. The format will
        be controlled by the value of the verbose bool argument.

        - verbose == False

          Display a pretty version. A pretty version is the Element
          contents formatted as-if within an HTML tag.

        - verbose == True

          Display the pretty version, but prefixed with a selection of
          Element attributes such as the Source and ElementState
          names.
        """

        if not debugging():
            return

        style = 'verbose' if verbose else 'pretty'

        header = '-' * 10
        header += f' {style} {label} '
        header += '-' * 10
        print(header, file=log.target)

        #
        # :NOTE: Deleted elements are dumped for debugging and
        # informational purposes. Currently, there will be no deleted
        # elements prior to handling duplicates.
        #
        elements = self.ordered_elements
        for element in iter(elements):
            #
            # Always use SPACE mode indentation using 4 spaces per
            # level.
            #
            ws = make_whitespace(mode=IndentationMode.SPACE,
                                 depth=element.nesting_depth)
            if verbose:
                out = element.verbose_str()
            else:
                out = element.pretty_str()
            print('{}{}'.format(ws, out), file=log.target)

    def debug_dump_duplicates(self, label):
        """Display the couht of duplicate Elements.

        This method is a no-op when the debug_level == 0.

        Keyword arguments:
        label - the text to place in the header before display the
                Elements.

        Iterate over each entry in the by_path dictionary. If the sum
        of the number of Elements in each entry's Source lists is more
        than 0, then display the count and the key. Since the key will
        encode the parent path with either the folder name or the
        anchor href, this is adequate for seeing which Elements have
        duplicates.
        """

        if not debugging():
            return

        header = '-' * 10
        header += f' {label} '
        header += '-' * 10
        print(header, file=log.target)

        by_path = self.by_path
        for key in iter(by_path):
            n = 0
            for source in Source:
                element_list = by_path[key].element_list(source=source)
                n += len(element_list)

            if n > 1:
                print('{} duplicates for key {}'.format(n,
                                                        key),
                      file=log.target)

class BookmarksParser(HTMLParser):
    """Parse, clean, and canonicalize an HTML bookmarks file.

    Parse a bookmarks file and store the data necessary for performing
    the merging process.

    This parser can handle files that lack DOCTYPE
    netscape-bookmark-file-1 when requested, but the same cleanup and
    formatting will occur as-if it is an HTML bookmarks file. Even
    files without a DOCTYPE declaration can be cleaned and
    canonicalized.

    The _bookmarks_only behavior cannot be enforced until the DOCTYPE
    is found or the entire input file is read.

    The following attributes from the MergingContext are used:

    _args.convert - specify how to handle entityrefs and charrefs.
    _args.bookmarks_only - only accept bookmarks formatted HTML.
    _args.Inline_log - send debugging output inline with the parsed
                       output in the I/O buffer instead of to stdout.

    By default, the HTMLParser will convert entityrefs and charrefs to
    their unescaped form. Unfortunately, the HTML used in a bookmarks
    file does not use entityrefs and charrefs correctly. Override the
    default behavior and handle entityrefs and charrefs ourselves. The
    HTMLParser default behvior can be enabled using --no-convert.

    Public methods:
    file - getter
    source - getter
    bookmarks - getter
    dl_depth - getter
    bookmarks_style - getter
    bookmarks_style(BookmarksStyle) - setter
    folder_open - getter
    folder_open(bool) - setter
    folder - getter
    folder(string) - setter
    is_bookmarks_doc - predicate

    handle_starttag - overridden HTMLParser method.
    handle_endtag - overridden HTMLParser method.
    handle_data - overridden HTMLParser method.
    handle_comment - overridden HTMLParser method.
    handle_decl - overridden HTMLParser method.
    handle_entityref - overridden HTMLParser method.
    handle_charref - overridden HTMLParser method.
    handle_pi - overridden HTMLParser method.
    unknown_decl - overridden HTMLParser method.
    
    close - close the HTMLParser and finalize the parsing.

    Public debugging methods:
    debug_attrs_found - display the list of HTML element attributes
                        encountered.

    Private methods:
    _tag_to_upper - convert a tag to uppercase when that is the
                    preferred form.
    _keep_attr - return whether an attribute in an element should be
                 retained.
    _style_set - determine and set the BookmarksStyle.
    """

    global log

    def __init__(self, context, file, source, bookmarks):
        """Create and initialize an instance of a BookmarksParser.

        Keyword arguments:
        context - a MergingContext holding attributes used by this
                  parser and the settings from the arguments passed to
                  the script.
        file - the name of the HTML bookmarks file.
        source - the Source tag for the input. This is one of PRIMARY
                 and SECONDARY.
        bookmarks - an instance of a Bookmarks class.
        """

        self._args = context._args
        super().__init__(convert_charrefs=self._args.convert)
        self._file = file
        self._source = source

        #
        # Post-parsing state and information.
        #
        self._bookmarks = bookmarks
        self._is_bookmarks_doc = False
        self._bookmarks_only = self._args.bookmarks_only
        #
        # Empty string since it is incrementally appended.
        #
        self._h1_contents = ''

        #
        # State maintained during parsing.
        #
        self._io_buffer = io.StringIO()
        if self._args.Inline_log:
            log.target = self._io_buffer

        #
        # The style of an HTML bookmarks file. :NOTE: This is not yet
        # used. One potential future use is for style of the generated
        # output of a new bookmarks file.
        #
        self._bookmarks_style = None

        #
        #
        # This is the actual depth of the <dl> tags.
        #
        self._dl_depth = 0

        #
        # One or more <dl> tags may be present prior to the first <h3>
        # element for a folder. The dl_depth needs to be adjusted to
        # be the actual nesting depth of the folder. In other words,
        # the first folder, and the ones at the same top-level
        # dl_depth, should be adjusted to have a folder nesting depth
        # of 0.
        #
        self._adj_dl_depth = 0

        #
        # Accumulate the dl_depth adjustment until the first <h3>
        # element for a folder is found. When the folder is found, the
        # accumulation is done.
        #
        self._adjustment_done = False

        #
        #  The <h1>...</h1> tag header is not a folder, but store it.
        #
        self._h1_open = False

        #
        # Folder names are within <h3>...</h3>
        #
        self._folder_open = False

        #
        # The empty string since it is incrementally appended. Parser
        # data, entityrefs, and charrefs need to be accumulated to
        # form the complete folder name.
        #
        self._tmp_folder = ''
        self._folder = None
        #
        # Safari always uses an "id" attribute for the "Reading List"
        # folder in a <h3> attribute. Otherwise, this will be None.
        #
        self._id_attr = None

        #
        # All of the folders and the current folder comprising the
        # full path of a folder. The deque is the components of the
        # path without an separators such as '/'.
        #
        self._folder_path = deque()

        #
        # Anchor elements are within <a>...</a>.
        #
        self._anchor_open = False

        #
        # The empty string since it is incrementally appended. Parser
        # data, entityrefs, and charrefs need to be accumulated to
        # form the complete anchor text.
        #
        self._anchor_text = ''
        self._href = None

        #
        # For debugging support.
        #
        self._found_attrs = dict()

    @property
    def file(self):
        return self._file

    @property
    def source(self):
        return self._source

    @property
    def bookmarks(self):
        return self._bookmarks

    @property
    def is_bookmarks_doc(self):
        return self._is_bookmarks_doc

    @property
    def dl_depth(self):
        return self._dl_depth

    @property
    def bookmarks_style(self):
        return self._bookmarks_style

    @bookmarks_style.setter
    def bookmarks_style(self, style):
        self._bookmarks_style = style

    @property
    def folder_open(self):
        return self._folder_open

    @folder_open.setter
    def folder_open(self, value):
        """Set internal state when encountering <h3> and </h3>.

        This is a setter that performs a complex sequence of actions.

        When <h3> is encountered, mark that the contents of a folder
        name is beginning. The accumulation is complete when </h3> is
        encountered.

        The boolean sequence of encountering <h3> and </h3> must be:
        True, False, True, False.
        """

        debugmsg(2,
                 log.target,
                 '  old folder_open {} new folder_open {}\n',
                 self._folder_open,
                 value)

        if self._folder_open == value:
            if value:
                raise AttributeError('Nested folder open')
            else:
                raise AttributeError('No folder open')

        self._folder_open = value
        #
        # The full name of the folder has been accumulated. Replace
        # any '/' characters with a charref. Store name and clear the
        # temporary folder.
        #
        if not value:
            folder = self._tmp_folder
            if re.search(r'/', folder):
                debugmsg(1, log.target, '  / in {}\n', folder)
                folder = re.sub(r'/', '&#47;', folder)

            self.folder = folder
            self._tmp_folder = ''

    @property
    def folder(self):
        return self._folder

    @folder.setter
    def folder(self, folder):
        """Set the name of the current folder.

        This is a setter that performs a complex sequence of actions.

        When the definition of a folder name is complete, update all
        of the state associated with the folder as a container.
        """

        folder_path = self._folder_path
        path_len = len(folder_path)
        nesting_depth = self.dl_depth - self._adj_dl_depth

        debugmsg(2,
                 log.target,
                 ('  using folder_path {} path_len {} ' +
                  'dl_depth {} nesting_depth {}\n'),
                 folder_path,
                 path_len,
                 self.dl_depth,
                 nesting_depth)

        path_list = list(folder_path)
        element = Folder(source=self.source,
                         nesting_depth=nesting_depth,
                         parent_path=make_path(path_list=path_list),
                         folder=folder,
                         id=self._id_attr)

        bookmarks = self.bookmarks
        bookmarks.update_elements(element=element)

        self._folder = folder
        self._id_attr = None
        folder_path.extend([folder])

        debugmsg(1,
                 log.target,
                 '  setting folder "{}" with folder_path {}\n',
                 self._folder,
                 self._folder_path)

    def close(self):
        """Close the I/O buffer used for the parsed HTML content.

        Parsing the HTML bookmarks input file is complete. Close the
        I/O buffer where the parse results were written. Also, perform
        the close() operation in the base class.

        Since the debug logging may also be going to the same I/O
        buffer, set the log target to stdout.
        """

        debugmsg(1, log.target, 'closing input\n')

        #
        # Save the now cleaned HTML bookmarks and discard the I/O
        # buffer.
        #
        text = self._io_buffer.getvalue()
        self._io_buffer.close()
        self._io_buffer = None
        self._bookmarks.text = text

        super().close()
        #
        # The log target must be set to a valid handle.
        #
        log.target = sys.stdout

        debugmsg(1, log.target, 'input is closed\n')

    def handle_starttag(self, tag, attrs):
        """Perform the HTMLParser handle_starttag operation."""

        debugmsg(1, log.target, 'handle start tag = {}\n', tag)

        #
        # Look for start tag of <tag>...</tag> attributes whose
        # content is extracted and used for later processing.
        #
        tag_lower = tag.lower()
        #
        # macOS Ventura (13.6) has Python 3.9.
        # Python 3.10+ supports match.
        #
        if tag_lower == 'h1':
            fail_when(self._h1_contents,
                      'duplicate H1 tag ' + f'"{self._h1_contents}"',
                      where=self.file)
            self._h1_open = True
        elif tag_lower == 'h3':
            self.folder_open = True
        elif tag_lower == 'a':
            self._anchor_open = True
        elif tag_lower == 'dl':
            self._dl_depth += 1
            if not self._adjustment_done:
                self._adj_dl_depth += 1
            debugmsg(2,
                     log.target,
                     '  inc dl_depth {} adj_dl_depth {} folder_path {}\n',
                     self.dl_depth,
                     self._adj_dl_depth,
                     self._folder_path)

        to_upper = self._tag_to_upper(tag=tag)

        if len(attrs) == 0:
            out_text = self.get_starttag_text()
            if to_upper:
                out_text = out_text.upper()

            debugmsg(1,
                     log.target,
                     '  attrs len == 0 out_text = {}\n',
                     out_text)

            print(out_text, end='', file=self._io_buffer)
            return

        #
        # Accumulate the attributes that we will retain for the tag.
        #
        retained = []
        for attr in attrs:
            name, value = attr
            self._found_attrs[name] = name
            #
            # Use an attribute even if not retained. For example, used
            # the FOLDED attribute if found.
            #
            self._style_set(what='attr',
                            contents=name,
                            extra_contents=value)
            if self._keep_attr(name=name):
                retained.append(attr)

                if debugging(2):
                    if name.lower() == 'href':
                        debugmsg(2,
                                 log.target,
                                 '  retained href {}\n',
                                 value)

        out_tag = tag
        if self._tag_to_upper(tag=tag):
            out_tag = tag.upper()

        debugmsg(1, log.target, '  final out_tag = {}\n', out_tag)

        #
        # Print the tag start open indicator and tag.
        #
        print('<{}'.format(out_tag), end='', file=self._io_buffer)

        #
        # Print the retained attributes.
        #
        for attr in retained:
            name, value = attr
            if name.lower() == 'href':
                self._href = value
            elif name.lower() == 'id':
                self._id_attr = value

            #
            # Assuming all attributes are uppercase.
            #
            print(' {}="{}"'.format(name.upper(), value),
                  end='',
                  file=self._io_buffer)

        #
        # Print the tag start close indicator.
        #
        print('>', end='', file=self._io_buffer)

    def handle_endtag(self, tag):
        """Perform the HTMLParser handle_endtag operation."""

        debugmsg(1, log.target, 'handle end tag = {}\n', tag)
        tag_lower = tag.lower()

        #
        # Look for end tags for <tag>...</tag> attributes whose
        # content is extracted and used for later processing.
        #
        # macOS Ventura (13.6) has Python 3.9.
        # Python 3.10+ supports match.
        #
        if tag_lower == 'h1':
            self._h1_open = False
            self._style_set(what='h1', contents=self._h1_contents)
        elif tag_lower == 'h3':
            self.folder_open = False
            #
            # The dl_depth adjustment accumulation is now done.
            #
            self._adjustment_done = True
        elif tag_lower == 'a':
            if not self._anchor_open:
                raise Exception(f'End tag {tag} without start tag')

            parent_path = make_path(path_list=list(self._folder_path))
            nesting_depth = self.dl_depth - self._adj_dl_depth
            self.bookmarks.add_anchor(source=self.source,
                                      nesting_depth=nesting_depth,
                                      parent_path=parent_path,
                                      href=self._href,
                                      anchor_text=self._anchor_text)

            self._href = None
            self._anchor_text = ''
            self._anchor_open = False
        elif tag_lower == 'dl':
            self._dl_depth -= 1
            #
            # The current folder is complete, so return to the
            # previous folder, i.e. the current folder's immediate
            # parent. :NOTE: <dl> tags can introduce nesting without
            # creating a folder, so check the path length.
            #
            if len(self._folder_path) > 0:
                self._folder_path.pop()

            debugmsg(2,
                     log.target,
                     '  dec dl_depth {} adj_dl_depth {} folder_path {}\n',
                     self.dl_depth,
                     self._adj_dl_depth,
                     self._folder_path)

        out_tag = tag
        if self._tag_to_upper(tag=tag):
              out_tag = tag.upper()

        print('</{}>'.format(out_tag), end='', file=self._io_buffer)

    def handle_data(self, data):
        """Perform the HTMLParser handle_data operation.

        Some element contents such as anchor text, folder names,
        etc. are handled as data. Special processing is necessary for
        some of these data items. When no special processing is
        required, the data is simply appended to the I/O buffer.
        """

        is_ws = data.isspace()
        self._style_set(what='data', contents=data)

        if debugging(2):
            #
            # Indicate, but suppress strings of whitespace, including
            # newlines.
            #
            if is_ws:
                dbg_data = '...ws...'
            else:
                dbg_data = data
            debugmsg(2, log.target, 'handle data = |{}|\n', dbg_data)

        #
        # Accumulate the string for elements where the full contents
        # are extracted for use later.
        #
        if self._h1_open:
            self._h1_contents += data
            debugmsg(1,
                     log.target,
                     '  data h1_contents |{}|\n',
                     self._h1_contents)
        elif self.folder_open:
            self._tmp_folder += data
            debugmsg(1,
                     log.target,
                     '  data tmp_folder |{}|\n',
                     self._tmp_folder)
        elif self._anchor_open:
            self._anchor_text += data
            debugmsg(1,
                     log.target,
                     '  data anchor_text |{}|\n',
                     self._anchor_text)

        print(data, end='', file=self._io_buffer)

    def handle_comment(self, comment):
        """Perform the HTMLParser handle_comment operation.

        Comments are stripped from the cleaned and canonicalized HTML
        bookmarks.
        """

        debugmsg(1, log.target, 'handle comment <!--{}-->\n', comment)
        self._style_set(what='comment', contents=comment)

    def handle_decl(self, decl):
        """Perform the HTMLParser handle_decl operation.

        The HTML DOCTYPE is a declaration.
        """

        debugmsg(1, log.target, 'handle decl {}\n', decl)
        if re.match(r'doctype ', decl, flags=re.IGNORECASE):
            debugmsg(1, log.target, '  doctype = {}\n', decl)

            for i, word in enumerate(re.split(r'\s+', decl)):
                debugmsg(2, log.target, '  decl item {} {}\n', i, word)

                if re.fullmatch(r'netscape-bookmark-file-1',
                                word,
                                flags=re.IGNORECASE):
                    self._is_bookmarks_doc = True

        debugmsg(1,
                 log.target,
                 '  _is_bookmarks_doc {} _bookmarks_only {}\n',
                 self._is_bookmarks_doc,
                 self._bookmarks_only)

        if not self.is_bookmarks_doc and self._bookmarks_only:
            sys.exit(f'{self.file} is not an HTML bookmarks file.')

        print('<!{}>'.format(decl), end='', file=self._io_buffer)

    #
    # It appears that:
    #
    # A Safari bookmarks file uses entityrefs, e.g. & as &amp;, but
    # not charrefs, e.g. ' as ' and not &#39;. For ' and ", Safari
    # does not use an entityref either.
    #
    # A Firefox bookmarks file always uses both entityrefs and
    # charrefs.
    #

    def handle_entityref(self, name):
        """Perform the HTMLParser handle_entityref operation.

        The convert_charrefs flag controls converting both entityrefs
        and charrefs. It appears that Safari uses some entityrefs, but
        not charrefs. Firefox uses both. I'm assuming that Firefox
        will handle importing a bookmarks file without charrefs.
        """

        debugmsg(1, log.target, 'handle entityref |{}|\n', name)
        if name == 'quot':
            out_s = html.unescape(f'&{name};')
            out_s = '{}'.format(out_s)
        else:
            out_s = '&{};'.format(name)

        #
        # Accumulate the string for elements where the full contents
        # are extracted for use later.
        #
        # :NOTE: Currently this assumes there are no entityrefs in
        # <h1> elements.
        #
        if self.folder_open:
            self._tmp_folder += out_s
            debugmsg(1,
                     log.target,
                     '  entityref tmp_folder |{}|\n',
                     self._tmp_folder)
        elif self._anchor_open:
            self._anchor_text += out_s
            debugmsg(1,
                     log.target,
                     '  entityref anchor_text |{}|\n',
                     self._anchor_text)

        print(out_s, end='', file=self._io_buffer)

    #
    # See details above about handling conversion and how charrefs are
    # used in different bookmarks files.
    #
    def handle_charref(self, name):
        """Perform the HTMLParser handle_charref operation.

        The convert_charrefs flag controls converting both entityrefs
        and charrefs. It appears that Safari uses some entityrefs, but
        not charrefs. Firefox uses both. I'm assuming that Firefox
        will handle importing a bookmarks file without charrefs.
        """

        #
        # :NOTE: Assuming no charrefs in <h1> elements.
        #
        debugmsg(1, log.target, 'handle charref |{}|\n', name)
        out_s = html.unescape(f'&#{name};')
        if self.folder_open:
            self._tmp_folder += out_s
            debugmsg(1,
                     log.target,
                     '  charref tmp_folder |{}|\n',
                     self._tmp_folder)
        elif self._anchor_open:
            self._anchor_text += out_s
            debugmsg(1,
                     log.target,
                     '  charref anchor_text |{}|\n',
                     self._anchor_text)

        print(out_s, end='', file=self._io_buffer)

    def handle_pi(self):
        unimplemented(self.__qualname__)

    def unknown_decl(self):
        unimplemented(self.__qualname__)

    def _tag_to_upper(self, tag):
        """Return whether to emit a tag should be emitted as upper case.

        This is primarily for a unified, cosmetic appearance.
        """

        upper_case = True
        if tag.lower() == 'p':
            upper_case = False

        return upper_case

    def _keep_attr(self, name):
        """Return whether to retain an attribute of an HTML element.

        By default, an attribute is retained. The attributes matched
        here are the ones to drop.
        """

        keep = True
        #
        # macOS Ventura (13.6) has Python 3.9.
        # Python 3.10+ supports match.
        #
        lc_name = name.lower()
        if (lc_name == 'add_date' or
            lc_name == 'last_modified' or
            lc_name == 'icon_uri' or
            lc_name == 'icon' or
            lc_name == 'folded'):
            keep = False

        return keep

    def _style_set(self, what, contents, extra_contents=''):
        """Determine the BookmarksStyle from a property's contents.

        Keyword arguments:
        what - the name of the property for analysis.
        contents - the property contents for analysis.
        extra_contents - the optional extra property contents for
                         analysis.

        An HTML bookmarks file may be from Safari, Firefox, or HTML
        that is not formatted and styled for either. As selected
        properties, such as an HTML element attribute, a comment,
        etc., are encountered, they are examined to see which style
        uses the value in the contents.

        These heuristics are not performed when processing an HTML
        file that may not follow the expected conventions of an
        HTML bookmarks file.

        Once the initial style is determined, it may not change. In
        other words, an HTML bookmarks file cannot use a mixture of
        Safari and Firefox conventions.

        :NOTE: Currently, the style is not used for anything. One
        future application could be for defining the style of the
        generated output HTML bookmarks.

        :TODO: A future enhancement could add the notion of an
        undetermined style. A script option could be used to specify
        that the style does not matter. This option would not disable
        enforcing that the HTML file must follow the expected
        conventions of an HTML bookmarks file.
        """

        #
        # An arbitrary choice when the file will not be analyzed for a
        # style.
        #
        if not self._bookmarks_only:
            self.bookmarks_style = BookmarksStyle.FIREFOX
            return

        cur_style = self.bookmarks_style
        file = self.file
        is_set = True if cur_style != None else False
        style = None

        #
        # macOS Ventura (13.6) has Python 3.9.
        # Python 3.10+ supports match.
        #
        what_lower = what.lower()
        if (what_lower == 'comment' and
            re.search(r'DO NOT EDIT!', contents, re.MULTILINE)):
            fail_when(is_set and cur_style != BookmarksStyle.FIREFOX,
                      f'unexpected comment "{contents}"',
                      where=file)
            style = BookmarksStyle.FIREFOX
        elif what_lower == 'data':
            #
            # Safari uses TABS for indentation.
            #
            has_tab = re.search(r'\t', contents, re.MULTILINE)
            if has_tab and contents.isspace():
                fail_when(is_set and cur_style != BookmarksStyle.SAFARI,
                          'unexpected TAB',
                          where=file)
                style = BookmarksStyle.SAFARI
        elif what_lower == 'attr':
            contents_lower = contents.lower()
            if 'folded' == contents_lower:
                fail_when(is_set and cur_style != BookmarksStyle.SAFARI,
                          f'unexpected folded attribute "{contents_lower}"',
                          where=file)
                style = BookmarksStyle.SAFARI
            elif (contents_lower == 'add_date' or
                  contents_lower == 'last_modified' or
                  contents_lower == 'icon_uri' or
                  contents_lower == 'icon'):
                fail_when(is_set and cur_style != BookmarksStyle.FIREFOX,
                          f'unexpected attr "{contents}"',
                          where=file)
                style = BookmarksStyle.FIREFOX
            elif (contents_lower == 'http-equiv' and
                  re.search(r'content-security-policy',
                            extra_contents,
                            flags=re.IGNORECASE)):
                fail_when(is_set and cur_style != BookmarksStyle.FIREFOX,
                          ('unexptected attr ' + f'"{contents}" ' +
                           f'"{extra_contents}"'),
                           where=file)
                style = BookmarksStyle.FIREFOX
        elif what_lower == 'html':
                fail_when(is_set and cur_style != BookmarksStyle.SAFARI,
                          'unexpected HTML tag',
                          where=file)
                style = BookmarksStyle.SAFARI
        elif what_lower == 'h1':
            if re.fullmatch(r'bookmarks', contents, flags=re.IGNORECASE):
                style = BookmarksStyle.SAFARI
            elif (re.fullmatch(r'bookmarks menu',
                               contents,
                               flags=re.IGNORECASE)):
                style = BookmarksStyle.FIREFOX
            else:
                fail_always('unrecognized h1 contents ' + contents,
                            where=file)

        debugmsg(3,
                 log.target,
                 '  cur_style {} style {} inputs "{}" "{}" "{}"\n',
                 cur_style,
                 style,
                 what,
                 contents,
                 extra_contents)

        #
        # If none of the checks above fail, then set the style. When
        # style is not allowed to change, perform that check above.
        #
        if style != None and style != cur_style:
            debugmsg(1,
                     log.target,
                     '  bookmarks_style from {} to {}\n',
                     cur_style,
                     style)
            self.bookmarks_style = style

    def debug_attrs_found(self):
        """Display the HTML element attributes encountered during parsing.

        This method is a no-op when the debug_level == 0.

        A summary of all of the attributes encountered reveals whether
        there are any attributes which were either not used or
        explicitly ignored.
        """

        if not debugging():
            return
        if len(self._found_attrs) == 0:
            return
            
        for attr in iter(self._found_attrs):
            debugmsg(1, log.target, 'found attr {}\n', attr)

class MergingContext:
    """A class for holding the state for merging HTML bookmarks files.

    The merging operates in 1 of 2 modes:

    - Merge 2 HTML bookmarks files.
    - Merge 1 HTML bookmark file with an empty file.

    When an HTML bookmarks file is loaded, it is parsed for extracting
    and storing the Folder and Anchor elements. Additional metadata
    and attributes for the merging operation and its results are also
    extracted.

    After the 1 or 2 HTML bookmarks files are parsed, the merging
    operation will yield an ElementTree holding the merged
    results. For the case when only 1 file is given, the merged tree
    is a copy of the ElementTree for the PRIMARY source.

    Public methods:
    primary_file - getter
    primary_bookmarks - getter
    secondary_file - getter
    secondary_bookmarks - getter
    merged - getter
    
    run - execute the requested merging operation.

    Public debugging methods:
    debug_parsed_text - display the raw text of the canonicalized and
                        cleaned HTML created during parsing.
    debug_count_unique - count the number of unique bookmarks
                         Elements.

    Private methods:
    _load - read and parse an HTML bookmarks file.
    _load_source_files - load both HTML bookmarks files.
    _choose_bookmark - select the bookmark to use from a list.
    _resolve_duplicates - select a single bookmark from each set of
                          duplicates.
    _is_parent_deleted - return whether the folder containing an
                         Element is deleted.
    _ask_delete - ask for confirmation when a bookmark may be deleted.
    _resolve_deletions - determine which bookmarks only present in the
                         SECONDARY_BOOKMARKS should be deleted and
                         delete them when confirmed.
    _element_to_use - return the Element to use from a set of
                      duplicates.
    _merge_trees - merge 2 trees of bookmarks Elements.
    _merge_bookmarks - resolve duplicates and deletions and merge the
                       trees of bookmarks Elements.
    _print_prologue - print the HTML before the HTML bookmarks
                      entries.
    _print_bookmarks - print the HTML bookmarks entries.
    _print_epilogue - print the HTML after the bookmarks entries.
    _generate_bookmarks - generate and print the HTML for the
                          bookmarks file.
    """

    global log

    def __init__(self):
        """Construct and initialize a MergingContext instance."""
        self._primary_file = None
        self._primary_bookmarks = None
        self._secondary_file = None
        self._secondary_bookmarks = None

        #
        # When false, there is no prompting for selecting duplicates
        # and deleting bookmarks. The default answer is always used.
        #
        self._interactive = False

        #
        # Create an empty ElementTree for holding the merged results.
        #
        self._merged = ElementTree(item=Folder(source=Source.BOTH,
                                               nesting_depth=-1,
                                               parent_path='',
                                               folder='/'))

        #
        # Create an ArgumentParser and execute argument parsing.
        #
        args_parser = argparse.ArgumentParser()
        #
        # :TODO: Support writing to an output file. If a common format
        # doesn't work with both browsers, then generate Safari style
        # and Firefox style output files.
        #
        args_parser.add_argument(
            '--convert', '-c',
            action=argparse.BooleanOptionalAction,
            default=False,
            help='convert entityrefs, but not charrefs')

        args_parser.add_argument(
            '--bookmarks-only', '-b',
            action=argparse.BooleanOptionalAction,
            default=True,
            help='only accept HTML bookmarks as indicated by the DOCTYPE')

        args_parser.add_argument(
            '--interactive', '-i',
            action=argparse.BooleanOptionalAction,
            default=False,
            help='interactively merge bookmarks')

        args_parser.add_argument(
            '--out', '-o',
            nargs='?',
            type=argparse.FileType('w'),
            default=sys.stdout,
            help='output destination of the merged HTML bookmarks')

        args_parser.add_argument(
            '--Debug', '-D',
            action='count',
            default=0,
            help='each occurence increments the debugging level by 1')

        args_parser.add_argument(
            '--Inline-log', '-I',
            action=argparse.BooleanOptionalAction,
            default=False,
            help='debugging messages are inline with the parsed output')

        args_parser.add_argument(
            'primary',
            metavar='primary-bookmarks | bookmarks-to-clean',
            action='store',
            nargs=1,
            help='Primary HTML bookmarks files to merge or clean')
        args_parser.add_argument(
            'secondary',
            metavar='secondary-bookmarks',
            action='store',
            nargs='?',
            # Be explicit
            default=None,
            help='Secondary HTML bookmarks files to merge')

        self._args = args_parser.parse_args()
        global debug_level
        debug_level = self._args.Debug
        self._interactive = self._args.interactive
        self._bookmarks_out = self._args.out

        #
        # A single input file means to canonicalize and clean the HTML
        # in the file. This is achieved by merging against an empty
        # secondary file.
        #
        if self._args.secondary == None:
            self._args.secondary = '/dev/null'
            self._args.bookmarks_only = False

        debugmsg(1, sys.stdout, 'debug_level = {}\n', debug_level)

    @property
    def primary_file(self):
        return self._primary_file

    @property
    def primary_bookmarks(self):
        return self._primary_bookmarks

    @property
    def secondary_file(self):
        return self._secondary_file

    @property
    def secondary_bookmarks(self):
        return self._secondary_bookmarks

    @property
    def merged(self):
        return self._merged

    def debug_parsed_text(self, text):
        """Display the raw text generated by parsing the input file.

        This method is a no-op when the debug_level == 0.

        Keyword arguments:
        text - the text string containing canonicalized and cleaned
               HTML.

        :NOTE: When debugging and inline logging is enabled, the
        debugging messages are interspersed with the HTML.
        """

        if not debugging():
            return

        #
        # The text will can contain both debugging messages as well as
        # the cleaned and canonicalized HTML bookmarks.
        #
        debugmsg(1, sys.stdout, '===>\n')
        print(text, end='', file=sys.stdout)
        debugmsg(1, sys.stdout, '<===\n')

    def debug_count_unique(self):
        """Return the count the number of unique bookmark Elements.

        This method is a no-op when the debug_level == 0.

        An element is unique when its Source is not BOTH. This method
        counts everything in this Bookmarks ordered elements list that
        is not in BOTH. The results can be compared with the
        cumulative count of unique elements while processing the
        input.

        :NOTE: Deleted elements are counted for debugging and
        informational purposes. Currently, there are no deleted
        elements prior to resolving duplicates.
        """

        if not debugging():
            return 0

        num = len(self.primary_bookmarks.ordered_elements)

        elements = self.secondary_bookmarks.ordered_elements
        for element in iter(elements):
            if element.source != Source.BOTH:
                num += 1

        return num

    def _load(self, source, file, bookmarks):
        """Open, read, parse, and store an HTML bookmarks file.

        After parsing is complete, perform some consistency checks.
        When debugging, display various containers that were populated
        by the parsing.

        Keyword arguments:
        source - the PRIMARY or SECONDARY Source value for the input.
        file - the name of the HTML bookmarks input file.
        bookmarks - a Bookmarks class instance for storing the results
                    of parsing the input file.
        """

        fh  = FileHandle()
        fh.open(file=file)

        if fh.error != None:
            print(fh.error, file=sys.stderr)
            return 1

        parser = BookmarksParser(context=self,
                                 source=source,
                                 file=file,
                                 bookmarks=bookmarks)

        debugmsg(1, log.target, '----- processing {} -----\n', file)
        parser.feed(fh.handle.read())
        parser.debug_attrs_found()
        parser.close()

        #
        # Perform consistency checks. Fail the merging when any check
        # fails.
        #
        if not parser.is_bookmarks_doc and parser._bookmarks_only:
            sys.exit(f'{file} is not an HTML bookmarks file.')

        if parser.dl_depth > 0:
            sys.exit('{} {} DL elements still open.'.format(
                parser.file,
                parser.dl_depth))

        if parser.dl_depth < 0:
            sys.exit('{} {} extra closed DL elements.'.format(
                parser.file,
                parser.dl_depth))

        #
        # Display the contents of the Bookmarks containers populated
        # while parsing. Each of these methods is a no-op when not
        # debugging.
        #
        label = f'ordered list of elements {bookmarks.file} ' +\
            f'{bookmarks.num_unique} unique'
        bookmarks.debug_dump_ordered_elements(label=label)

        label = f'tree elements {bookmarks.file} ' +\
            f'{bookmarks.num_unique} unique'
        bookmarks.element_tree.debug_dump(label=label)

        label = 'by_path elements ' + bookmarks.file
        bookmarks.debug_dump_by_path(label=label)

        label = f'indented elements {bookmarks.file}'
        bookmarks.debug_dump_indented(label=label)
        bookmarks.debug_dump_indented(label=label, verbose=True)

        #
        # Note this for debugging purposes.
        #
        if parser.is_bookmarks_doc:
            debugmsg(1, log.target, 'a bookmarks file\n')
        else:
            debugmsg(1, log.target, '*not* a bookmarks file\n')

        return 0

    def _load_source_files(self):
        """Load and process the PRIMARY and SECONDARY input files."""

        self._primary_bookmarks = Bookmarks(file=self.primary_file,
                                            source=Source.PRIMARY,
                                            by_path=dict(),
                                            num_unique=0)
        status = self._load(source=Source.PRIMARY,
                            file=self.primary_file,
                            bookmarks=self.primary_bookmarks)

        if status != 0:
            return status

        self.debug_parsed_text(text=self.primary_bookmarks.text)
        primary_bookmarks = self.primary_bookmarks

        self._secondary_bookmarks = (
            Bookmarks(file=self.secondary_file,
                      source=Source.SECONDARY,
                      by_path=primary_bookmarks.by_path,
                      num_unique=primary_bookmarks.num_unique))
        status += self._load(source=Source.SECONDARY,
                             file=self.secondary_file,
                             bookmarks=self.secondary_bookmarks)

        if status != 0:
            return status

        #
        # This is a no-op when not debugging.
        #
        self.debug_parsed_text(text=self.secondary_bookmarks.text)

        return status

    def _choose_bookmark(self, interactive, choices):
        """Select and return 1 of 2 bookmarks from a list.

        The Element from the PRIMARY input is expected to be first.
        When non-interactive, the first Element of the list is
        selected.

        Keyword arguments:
        interactive - prompt for the selection when True.
        choices - the list of 2 Elements.
        """

        max = len(choices)
        fail_when(max != 2, str(max) + ' is not 2')
        max -= 1
        #
        # The first list is the default and selected when
        # non-interactive.
        #
        selected = -1 if interactive else 0
        default = str(0)
        marker = '*'

        while selected < 0:
            for (i, e) in enumerate(choices):
                #
                # When debugging, use the more verbose __str__() form.
                #
                if debugging():
                    out = f'{e}'
                else:
                    out = '{} {}'.format(e.source.name, e.pretty_str())
                print(f'{marker}{i} {out}')
                marker = ' '

            which = input(f'0 to {max} [{default}] ')
            which = which.lstrip().rstrip()
            if len(which) == 0:
                which = default

            if not which.isdigit():
                continue

            i = int(which)
            if i > max:
                continue

            selected = i

        return selected

    def _resolve_duplicates(self, by_path):
        """Eliminate duplicates when ther are multiple Anchors at a key.

        Look for Anchors with the same (parent_path, href) in the
        PRIMARY, SECONDARY, and BOTH lists. The anchor texts may be
        different, but the Anchors are considered to be the same.
        Determine which Anchors to retain.
        
        It's possible for an anchor to be in the both list, but
        duplicates are in the PRIMARY or SECONDARY list.
        """

        debugmsg(1, log.target, '_resolve_duplicates start\n')

        interactive = self._interactive
        num_resolved = 0

        for key in iter(by_path):
            p_list = by_path[key].element_list(source=Source.PRIMARY)
            s_list = by_path[key].element_list(source=Source.SECONDARY)
            b_list = by_path[key].element_list(source=Source.BOTH)

            #
            # There are no duplicates to handle when the PRIMARY and
            # SECONDARY lists are empty.
            #
            if len(p_list) == 0 and len(s_list) == 0:
                continue

            #
            # There are no duplicates when the BOTH list is empty and
            # one of the other lists is empty.
            #
            if len(b_list) == 0 and (len(p_list) == 0 or len(s_list) == 0):
                continue

            max_len = max(len(p_list), len(s_list), len(b_list))

            #
            # Pad each list to the same length
            #
            p_list.extend([None] * (max_len - len(p_list)))
            s_list.extend([None] * (max_len - len(s_list)))
            b_list.extend([None] * (max_len - len(b_list)))

            dbg_indent = ' ' * 6

            debugmsg(1,
                     log.target,
                     ('resolve dups before p_list {}\n' +
                      dbg_indent +
                      'resolve dups before s_list {}\n' +
                      dbg_indent +
                      'resolve dups before b_list {}\n'),
                     [e != None and e.verbose_str() for e in p_list],
                     [e != None and e.verbose_str() for e in s_list],
                     [e != None and e.verbose_str() for e in b_list])

            for i in range(max_len):
                p_elem = p_list[i]
                s_elem = s_list[i]
                b_elem = b_list[i]

                #
                # When an element is in both, delete the extras that
                # are in the PRIMARY and SECONDARY lists. :NOTE: this
                # is unconditional without prompting in interactive
                # mode.
                #
                if b_elem != None:
                    if p_elem != None:
                        p_elem.state = ElementState.DELETED
                    if s_elem != None:
                        s_elem.state = ElementState.DELETED
                    continue

                #
                # If one element is None and the other one is not,
                # then use the one that is not None.
                #
                if p_elem != None and s_elem == None:
                    continue
                if p_elem == None and s_elem != None:
                    continue

                #
                # A folder should never appear as a duplicate here,
                # but should have been in the BOTH list.
                #
                fail_when(p_elem != None and not p_elem.is_anchor,
                          'unexpected element type ' + p_elem.type.name)
                fail_when(s_elem != None and not s_elem.is_anchor,
                          'unexpected element type ' + s_elem.type.name)

                #
                # The default selection is the PRIMARY element, so
                # make it the first choice.
                #
                choices = [p_elem, s_elem]
                selected = self._choose_bookmark(interactive=interactive,
                                                 choices=choices)
                unselected = 1 - selected
                debugmsg(1,
                         log.target,
                         'selected {} {}\n',
                         selected,
                         choices[selected])

                #
                # This is only needed when the chosen element is in
                # the SECONDARY source, but it's harmless to always
                # set this.
                #
                choices[selected].dont_ask = True

                other_elem = choices[unselected]
                other_elem.state = ElementState.DELETED
                num_resolved += 1

            debugmsg(1,
                     log.target,
                     ('resolve dups after p_list {}\n' +
                      dbg_indent +
                      'resolve dups after s_list {}\n' +
                      dbg_indent +
                      'resolve dups after b_list {}\n'),
                     [e != None and e.verbose_str() for e in p_list],
                     [e != None and e.verbose_str() for e in s_list],
                     [e != None and e.verbose_str() for e in b_list])

        debugmsg(1,
                 log.target,
                 '_resolve_duplicates end {} resolved\n',
                 num_resolved)

    def _is_parent_deleted(self, element, by_path):
        """Return whether the folder containing the element is deleted.

        Keyword arguments:
        element - the element whose parent is checked.
        by_path - the by_path dictionary to use for checking.
        """

        parent_path = element.parent_path
        #
        # :TODO: Should this be a failure? Can the parent folder
        # element be absent?
        #
        if parent_path not in by_path:
            return True

        entry = by_path[parent_path]

        s_list = entry.element_list(Source.SECONDARY)
        b_list = entry.element_list(Source.BOTH)

        if len(b_list) != 0:
            return False

        fail_when(len(s_list) != 1,
                  (f'SECONDARY list at {parent_path} ' +
                   'does not have only 1 element'))

        folder = s_list[0]
        fail_when(not folder.is_folder(),
                  f'SECONDARY {element} at {parent_path} is not a folder')

        return folder.is_deleted()

    def _ask_delete(self, element, default='no'):
        """Return a bool after prompting whether to delete an Element.

        Keyword arguments:
        element - the Element to retain or delete.
        """

        ret = None

        while ret == None:
            #
            # When debugging, use the more verbose __str__() form.
            #
            if debugging():
                out = f'{element}'
            else:
                out = '{}'.format(element.pretty_str())
            response = input(f'{out}\ndelete? [{default}]? ')
            response = response.lstrip().rstrip()

            if len(response) == 0:
                response = default

            response = response.lower()
            if response == 'y':
                response = 'yes'
            elif response == 'n':
                response = 'no'

            if response == 'yes':
                ret = True
            elif response == 'no':
                ret = False

        return ret

    def _resolve_deletions(self, by_path):
        """Delete Elements only present in the SECONDARY source.

        Handle removing any elements which are only present in the
        SECONDARY bookmarks file. Nothing is deleted when running in
        non-interactive mode.

        Keyword arguments:
        by_path - a by_path dictionary from a Bookmarks instance.
        """

        interactive = self._interactive

        #
        # For now, delete nothing when in non-interactive mode.
        #
        if not interactive:
            return

        debugmsg(1,
                 log.target,
                 '_resolve_deletions start from {}\n',
                 Source.SECONDARY.name)

        num_resolved = 0
        for key in iter(by_path):
            p_list = by_path[key].element_list(source=Source.PRIMARY)
            s_list = by_path[key].element_list(source=Source.SECONDARY)

            if len(s_list) == 0:
                continue

            for element in s_list:
                if element == None:
                    continue
                if not element.is_saved():
                    continue
                if element.dont_ask:
                    debugmsg(1,
                             log.target,
                             'not deleting for dont_ask {}\n',
                             element)
                    continue

                yesno = None
                reason = ''
                parent_deleted = self._is_parent_deleted(element=element,
                                                         by_path=by_path)

                if parent_deleted:
                    reason = 'deleted via parent'
                    yesno = True

                if yesno == None:
                    yesno = self._ask_delete(element=element)
                    reason = 'deleted via user' if yesno else ''

                if yesno:
                    element.state = ElementState.DELETED
                    debugmsg(1,
                             log.target,
                             '{} {}\n',
                             reason,
                             element)

                #
                # Counted both deleted and retained.
                #
                num_resolved += 1

        debugmsg(1,
                 log.target,
                 '_resolve_deletions end from {} {} resolved\n',
                 Source.SECONDARY.name,
                 num_resolved)

    def _element_to_use(self, element, by_path):
        """Return the Element to use from a set of duplicates.

        Find the by_path entry at the key of the element parameter. If
        the passed element is a duplicate, then use heuristics for
        selecting an unhandled Element to use. The chosen Element can
        be the same as the passed element.

        Keyword arguments:
        element - the Element for comparing to a potential duplicate.
        by_path - the by_path dictionary to search.

        :NOTE: There are situations where there is no precise way to
        know when which pair of PRIMARY and SECONDARY Elements are
        duplicates. This is especially challenging when using
        about:blank hrefs as separators. Unless the bookmark is
        manually edited, the anchor text is also about:blank. In
        addition the same folder path in the PRIMARY and SECONDARY
        files may have differing numbers of about:blank separators.
        The consequence is that the chosen Element of a pair of
        duplicates may be incorrect and the generated HTML file may
        need to be manually fixed.
        """

        key = element.make_path_key()

        debugmsg(2,
                 log.target,
                 '_element_to_use element {} key {}\n',
                 element,
                 key)

        p_list = by_path[key].element_list(source=Source.PRIMARY)
        s_list = by_path[key].element_list(source=Source.SECONDARY)
        b_list = by_path[key].element_list(source=Source.BOTH)

        dbg_indent = ' ' * 6

        debugmsg(2,
                 log.target,
                 ('_element_to_use p_list {}\n' +
                  dbg_indent +
                  '_element_to_use s_list {}\n' +
                  dbg_indent +
                  '_element_to_use b_list {}\n'),
                 [e != None and e.verbose_str() for e in p_list],
                 [e != None and e.verbose_str() for e in s_list],
                 [e != None and e.verbose_str() for e in b_list])
        #
        # There are no duplicates when the PRIMARY and SECONDARY lists
        # are empty.
        #
        if len(p_list) == 0 and len(s_list) == 0:
            return None

        #
        # There are no duplicates when the BOTH list is empty and one
        # of the other lists is empty.
        #
        if len(b_list) == 0 and (len(p_list) == 0 or len(s_list) == 0):
            return None

        #
        # If the PRIMARY and SECONDARY lists are the same length, then
        # determine the index element parameter in the respective
        # source list. Use the element at that index in the other
        # list. We do not care about the state of the element
        # parameter. We only want to find its unhandled choice in the
        # other source list.
        #
        fail_when(not element.is_anchor(),
                  f'not an anchor {element}')
        which = -1
        if element.source == Source.PRIMARY:
            search_list = p_list
            other_list = s_list
        else:
            search_list = s_list
            other_list = p_list

        if len(p_list) == len(s_list):
            for i in range(len(p_list)):
                elem = search_list[i]
                if elem == None:
                    continue
                if (element == elem and
                    element.anchor_text == elem.anchor_text):
                    which = i
                    break

        if which >= 0:
            elem = None
            if (search_list[which] != None and
                search_list[which].is_saved()):
                elem = search_list[which]
            elif (other_list[which] != None and
                  other_list[which].is_saved()):
                elem = other_list[which]

            if elem != None:
                debugmsg(2,
                         log.target,
                         '_element_to_use return elem at which = {}\n',
                         which)
                return elem

        #
        # We did not yet find the duplicate to use, so search the
        # lists.
        #
        # Duplicates are in the order encountered. The PRIMARY list is
        # filled before the SECONDARY list. But, search the BOTH list
        # first since the element would have been moved to the BOTH
        # list. Return the first saved element found.
        #
        for elem in iter(b_list):
            if elem != None and elem.is_saved():
                return elem

        for elem in iter(p_list):
            if elem != None and elem.is_saved():
                return elem

        for elem in iter(s_list):
            if elem != None and elem.is_saved():
                return elem

        return None

    def _merge_trees(self,
                     src_root,
                     dst_tree,
                     by_path,
                     call_depth=1):
        """Merge the source tree into a destination ElementTree.

        Recursively traverse the tree at src_root and examine the
        Elements in the subtree. Insert the Elements in the SAVED
        state into the destination ElementTree.

        When an Element has a duplicate, the Element to use must be
        selected.

        Keyword arguments:
        src_root - the root of a tree to merge into the destination
                   ElementTree.
        dst_tree - the destination ElementTree where Elements from the
                   source tree are inserted.
        by_path - the by_path dictionary to use for selecting the
                  Element to use from a pair of duplicates.
        call_depth - used for debugging and incremented for a
                     recursive call.

        :NOTE: The Elements in the destination ElementTree may not be
        in the same order as they were in the source tree. They will
        be in the correct Folder, but may not be in the same relative
        order in the Folder.
        """

        fail_when((src_root.item != None and
                   not src_root.item.is_folder()),
                  'src root is not a folder')

        dbg_indent = ' ' * 6

        debugmsg(1,
                 log.target,
                 '_merge_trees call_depth {} src_root {}\n',
                 call_depth,
                 src_root)

        for node in iter(src_root.children):
            element = node.item

            debugmsg(1,
                     log.target,
                     '{} merge@1 {}\n',
                     element.nesting_depth,
                     element)

            to_use = self._element_to_use(element=element, by_path=by_path)

            if to_use != None:
                debugmsg(1,
                         log.target,
                         '{} merge@1 replacement {}\n',
                         to_use.nesting_depth,
                         to_use)
                element = to_use

            if element.is_saved():
                path_list = deque(element.parent_path.split(sep='/'))
                path_list.popleft()
                dst_tree.insert(element=element,
                                path_list=path_list)
                element.state = ElementState.HANDLED
                debugmsg(2,
                         log.target,
                         '{} merge@1 handled {}\n',
                         element.nesting_depth,
                         element)

            if element.is_folder():
                self._merge_trees(src_root=node,
                                  dst_tree=dst_tree,
                                  by_path=by_path,
                                  call_depth=call_depth+1)

    def _merge_bookmarks(self):
        """Merge 2 trees of bookmarks into a new tree.

        After resolving duplicates and deletions, merge the PRIMARY
        tree into a merged ElementTree. This will result in all SAVED
        Elements in the PRIMARY tree inserted into a merged
        ElementTree. Next, merge the SECONDARY tree into the same
        merged ElementTree. This second merge operation will insert
        the remaining SAVED Elements from the SECONDARY tree into the
        merged ElementTree.

        After the merging operation, examine the PRIMARY and SECONDARY
        bookmarks for any unhandled Elements. After merging, there
        should be no Element in the SAVED state.
        """

        if debugging():
            num_unique = self.debug_count_unique()
            debugmsg(1,
                     log.target,
                     'merging {} unique elements\n',
                     num_unique)

        primary_tree = self.primary_bookmarks.element_tree
        secondary_tree = self.secondary_bookmarks.element_tree

        #
        # The SECONDARY by_path dictionary is the PRIMARY by_path
        # dictionary combined with elements from the SECONDARY source.
        #
        by_path = self.secondary_bookmarks.by_path
        self._resolve_duplicates(by_path=by_path)
        self._resolve_deletions(by_path=by_path)

        label = 'primary tree after resolving duplicates and deletions'
        primary_tree.debug_dump(label=label)

        label = 'secondary tree after resolving duplicates and deletions'
        secondary_tree.debug_dump(label=label)

        if debugging():
            header = '-' * 10
            header += ' merging trees start '
            header += '-' * 10
            print(header, file=log.target)

        self._merge_trees(src_root=primary_tree.root,
                          dst_tree=self.merged,
                          by_path=by_path)
        self._merge_trees(src_root=secondary_tree.root,
                          dst_tree=self.merged,
                          by_path=by_path)

        if debugging():
            header = '-' * 10
            header += ' merging trees end '
            header += '-' * 10
            print(header, file=log.target)

        self.primary_bookmarks.verify_handled()
        self.secondary_bookmarks.verify_handled()

        return 0

    def _print_prologue(self, style, output):
        """Print the HTML prologue before the HTML bookmarks entries.

        Currently, Firefox style HTML is generated.

        Keyword arguments:
        style - the BookmarksStyle to use for generating the output.
        output - the output I/O handle.
        """

        fail_when(style != BookmarksStyle.FIREFOX,
                  f'only {BookmarksStyle.FIREFOX.name} style is supported')

        print('<!DOCTYPE NETSCAPE-Bookmark-file-1>', file=output)
        print('<!-- This is an automatically generated file.', file=output)
        print('     It will be read and overwritten.', file=output)
        print('     DO NOT EDIT! -->', file=output)
        print(('<META HTTP-EQUIV="Content-Type" ' +
               'CONTENT="text/html; charset=UTF-8">'),
              file=output)
        print(('<META HTTP-EQUIV="Content-Security-Policy" ' +
               'CONTENT="default-src ' + "'self'; script-src 'none'; " +
               'img-src data: *; ' + "object-src 'none'" + '"></META>'),
              file=output)
        print('<TITLE>Bookmarks</TITLE>', file=output)
        print('<H1>Bookmarks Menu</H1>', file=output)
        print('\n<DL><p>', file=output)

    def _print_bookmarks(self, style, output):
        """Print the HTML bookmarks entries.

        Currently, Firefox style HTML is generated.

        Keyword arguments:
        style - the BookmarksStyle to use for generating the output.
        output - the output I/O handle.
        """

        fail_when(style != BookmarksStyle.FIREFOX,
                  f'only {BookmarksStyle.FIREFOX.name} style is supported')

        self.merged.print_bookmarks(style=style, output=output)

    def _print_epilogue(self, style, output):
        """Print the HTML epilogue after the HTML bookmarks entries.

        Currently, Firefox style HTML is generated.

        Keyword arguments:
        style - the BookmarksStyle to use for generating the output.
        output - the output I/O handle.
        """

        fail_when(style != BookmarksStyle.FIREFOX,
                  f'only {BookmarksStyle.FIREFOX.name} style is supported')

        print('</DL>', file=output)

    def _generate_bookmarks(self):
        """Generate and print the HTML bookmarks from the merged tree."""

        self._print_prologue(style=BookmarksStyle.FIREFOX,
                             output=self._bookmarks_out)
        self._print_bookmarks(style=BookmarksStyle.FIREFOX,
                              output=self._bookmarks_out)
        self._print_epilogue(style=BookmarksStyle.FIREFOX,
                             output=self._bookmarks_out)

    def run(self):
        """Execute the merging operation."""

        args = self._args
        self._primary_file = args.primary[0]
        self._secondary_file = args.secondary

        status = self._load_source_files()

        if status != 0:
            return status

        label = f'duplicates from by_path ' + self._primary_file
        bookmarks = self.primary_bookmarks
        bookmarks.debug_dump_duplicates(label=label)

        label = f'duplicates from by_path ' +\
            self._secondary_file
        bookmarks = self.secondary_bookmarks
        bookmarks.debug_dump_duplicates(label=label)

        status = self._merge_bookmarks()

        if status != 0:
            return status

        label = 'merged elements'
        self.merged.debug_dump_with_tags(label=label)
        if debugging():
            print('-' * 50, file=log.target)

        self._generate_bookmarks()

        return status

def main():
    global log
    log = Log(log_target=sys.stdout)
    context = MergingContext()
    status = context.run()

    return status

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (KeyboardInterrupt, BrokenPipeError) as exc:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        pass
    except:
        # Ensure this happens.
        sys.stderr.flush()
        log.target.flush()
        # This can be the same as log.target.
        sys.stdout.flush()
        raise
