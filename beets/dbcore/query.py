# This file is part of beets.
# Copyright 2014, Adrian Sampson.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

"""The Query type hierarchy for DBCore.
"""
import re
from beets import util
from datetime import datetime, timedelta


class Query(object):
    """An abstract class representing a query into the item database.
    """
    def clause(self):
        """Generate an SQLite expression implementing the query.
        Return a clause string, a sequence of substitution values for
        the clause, and a Query object representing the "remainder"
        Returns (clause, subvals) where clause is a valid sqlite
        WHERE clause implementing the query and subvals is a list of
        items to be substituted for ?s in the clause.
        """
        return None, ()

    def match(self, item):
        """Check whether this query matches a given Item. Can be used to
        perform queries on arbitrary sets of Items.
        """
        raise NotImplementedError


class FieldQuery(Query):
    """An abstract query that searches in a specific field for a
    pattern. Subclasses must provide a `value_match` class method, which
    determines whether a certain pattern string matches a certain value
    string. Subclasses may also provide `col_clause` to implement the
    same matching functionality in SQLite.
    """
    def __init__(self, field, pattern, fast=True):
        self.field = field
        self.pattern = pattern
        self.fast = fast

    def col_clause(self):
        return None, ()

    def clause(self):
        if self.fast:
            return self.col_clause()
        else:
            # Matching a flexattr. This is a slow query.
            return None, ()

    @classmethod
    def value_match(cls, pattern, value):
        """Determine whether the value matches the pattern. Both
        arguments are strings.
        """
        raise NotImplementedError()

    def match(self, item):
        return self.value_match(self.pattern, item.get(self.field))


class MatchQuery(FieldQuery):
    """A query that looks for exact matches in an item field."""
    def col_clause(self):
        return self.field + " = ?", [self.pattern]

    @classmethod
    def value_match(cls, pattern, value):
        return pattern == value


class StringFieldQuery(FieldQuery):
    """A FieldQuery that converts values to strings before matching
    them.
    """
    @classmethod
    def value_match(cls, pattern, value):
        """Determine whether the value matches the pattern. The value
        may have any type.
        """
        return cls.string_match(pattern, util.as_string(value))

    @classmethod
    def string_match(cls, pattern, value):
        """Determine whether the value matches the pattern. Both
        arguments are strings. Subclasses implement this method.
        """
        raise NotImplementedError()


class SubstringQuery(StringFieldQuery):
    """A query that matches a substring in a specific item field."""
    def col_clause(self):
        pattern = (self.pattern
                       .replace('\\', '\\\\')
                       .replace('%', '\\%')
                       .replace('_', '\\_'))
        search = '%' + pattern + '%'
        clause = self.field + " like ? escape '\\'"
        subvals = [search]
        return clause, subvals

    @classmethod
    def string_match(cls, pattern, value):
        return pattern.lower() in value.lower()


class RegexpQuery(StringFieldQuery):
    """A query that matches a regular expression in a specific item
    field.
    """
    @classmethod
    def string_match(cls, pattern, value):
        try:
            res = re.search(pattern, value)
        except re.error:
            # Invalid regular expression.
            return False
        return res is not None


class BooleanQuery(MatchQuery):
    """Matches a boolean field. Pattern should either be a boolean or a
    string reflecting a boolean.
    """
    def __init__(self, field, pattern, fast=True):
        super(BooleanQuery, self).__init__(field, pattern, fast)
        if isinstance(pattern, basestring):
            self.pattern = util.str2bool(pattern)
        self.pattern = int(self.pattern)


class BytesQuery(MatchQuery):
    """Match a raw bytes field (i.e., a path). This is a necessary hack
    to work around the `sqlite3` module's desire to treat `str` and
    `unicode` equivalently in Python 2. Always use this query instead of
    `MatchQuery` when matching on BLOB values.
    """
    def __init__(self, field, pattern):
        super(BytesQuery, self).__init__(field, pattern)

        # Use a buffer representation of the pattern for SQLite
        # matching. This instructs SQLite to treat the blob as binary
        # rather than encoded Unicode.
        if isinstance(self.pattern, basestring):
            # Implicitly coerce Unicode strings to their bytes
            # equivalents.
            if isinstance(self.pattern, unicode):
                self.pattern = self.pattern.encode('utf8')
            self.buf_pattern = buffer(self.pattern)
        elif isinstance(self.pattern, buffer):
            self.buf_pattern = self.pattern
            self.pattern = bytes(self.pattern)

    def col_clause(self):
        return self.field + " = ?", [self.buf_pattern]


class NumericQuery(FieldQuery):
    """Matches numeric fields. A syntax using Ruby-style range ellipses
    (``..``) lets users specify one- or two-sided ranges. For example,
    ``year:2001..`` finds music released since the turn of the century.
    """
    def _convert(self, s):
        """Convert a string to a numeric type (float or int). If the
        string cannot be converted, return None.
        """
        # This is really just a bit of fun premature optimization.
        try:
            return int(s)
        except ValueError:
            try:
                return float(s)
            except ValueError:
                return None

    def __init__(self, field, pattern, fast=True):
        super(NumericQuery, self).__init__(field, pattern, fast)

        parts = pattern.split('..', 1)
        if len(parts) == 1:
            # No range.
            self.point = self._convert(parts[0])
            self.rangemin = None
            self.rangemax = None
        else:
            # One- or two-sided range.
            self.point = None
            self.rangemin = self._convert(parts[0])
            self.rangemax = self._convert(parts[1])

    def match(self, item):
        value = getattr(item, self.field)
        if isinstance(value, basestring):
            value = self._convert(value)

        if self.point is not None:
            return value == self.point
        else:
            if self.rangemin is not None and value < self.rangemin:
                return False
            if self.rangemax is not None and value > self.rangemax:
                return False
            return True

    def col_clause(self):
        if self.point is not None:
            return self.field + '=?', (self.point,)
        else:
            if self.rangemin is not None and self.rangemax is not None:
                return (u'{0} >= ? AND {0} <= ?'.format(self.field),
                        (self.rangemin, self.rangemax))
            elif self.rangemin is not None:
                return u'{0} >= ?'.format(self.field), (self.rangemin,)
            elif self.rangemax is not None:
                return u'{0} <= ?'.format(self.field), (self.rangemax,)
            else:
                return '1', ()


class CollectionQuery(Query):
    """An abstract query class that aggregates other queries. Can be
    indexed like a list to access the sub-queries.
    """
    def __init__(self, subqueries=()):
        self.subqueries = subqueries

    # Act like a sequence.

    def __len__(self):
        return len(self.subqueries)

    def __getitem__(self, key):
        return self.subqueries[key]

    def __iter__(self):
        return iter(self.subqueries)

    def __contains__(self, item):
        return item in self.subqueries

    def clause_with_joiner(self, joiner):
        """Returns a clause created by joining together the clauses of
        all subqueries with the string joiner (padded by spaces).
        """
        clause_parts = []
        subvals = []
        for subq in self.subqueries:
            subq_clause, subq_subvals = subq.clause()
            if not subq_clause:
                # Fall back to slow query.
                return None, ()
            clause_parts.append('(' + subq_clause + ')')
            subvals += subq_subvals
        clause = (' ' + joiner + ' ').join(clause_parts)
        return clause, subvals


class AnyFieldQuery(CollectionQuery):
    """A query that matches if a given FieldQuery subclass matches in
    any field. The individual field query class is provided to the
    constructor.
    """
    def __init__(self, pattern, fields, cls):
        self.pattern = pattern
        self.fields = fields
        self.query_class = cls

        subqueries = []
        for field in self.fields:
            subqueries.append(cls(field, pattern, True))
        super(AnyFieldQuery, self).__init__(subqueries)

    def clause(self):
        return self.clause_with_joiner('or')

    def match(self, item):
        for subq in self.subqueries:
            if subq.match(item):
                return True
        return False


class MutableCollectionQuery(CollectionQuery):
    """A collection query whose subqueries may be modified after the
    query is initialized.
    """
    def __setitem__(self, key, value):
        self.subqueries[key] = value

    def __delitem__(self, key):
        del self.subqueries[key]


class AndQuery(MutableCollectionQuery):
    """A conjunction of a list of other queries."""
    def clause(self):
        return self.clause_with_joiner('and')

    def match(self, item):
        return all([q.match(item) for q in self.subqueries])


class OrQuery(MutableCollectionQuery):
    """A conjunction of a list of other queries."""
    def clause(self):
        return self.clause_with_joiner('or')

    def match(self, item):
        return any([q.match(item) for q in self.subqueries])


class TrueQuery(Query):
    """A query that always matches."""
    def clause(self):
        return '1', ()

    def match(self, item):
        return True


class FalseQuery(Query):
    """A query that never matches."""
    def clause(self):
        return '0', ()

    def match(self, item):
        return False


# Time/date queries.

def _to_epoch_time(date):
    """Convert a `datetime` object to an integer number of seconds since
    the (local) Unix epoch.
    """
    epoch = datetime.fromtimestamp(0)
    delta = date - epoch
    try:
        return int(delta.total_seconds())
    except AttributeError:
        # datetime.timedelta.total_seconds() is not available on Python 2.6
        return delta.seconds + delta.days * 24 * 3600


def _parse_periods(pattern):
    """Parse a string containing two dates separated by two dots (..).
    Return a pair of `Period` objects.
    """
    parts = pattern.split('..', 1)
    if len(parts) == 1:
        instant = Period.parse(parts[0])
        return (instant, instant)
    else:
        start = Period.parse(parts[0])
        end = Period.parse(parts[1])
        return (start, end)


class Period(object):
    """A period of time given by a date, time and precision.

    Example: 2014-01-01 10:50:30 with precision 'month' represents all
    instants of time during January 2014.
    """

    precisions = ('year', 'month', 'day')
    date_formats = ('%Y', '%Y-%m', '%Y-%m-%d')

    def __init__(self, date, precision):
        """Create a period with the given date (a `datetime` object) and
        precision (a string, one of "year", "month", or "day").
        """
        if precision not in Period.precisions:
            raise ValueError('Invalid precision ' + str(precision))
        self.date = date
        self.precision = precision

    @classmethod
    def parse(cls, string):
        """Parse a date and return a `Period` object or `None` if the
        string is empty.
        """
        if not string:
            return None
        ordinal = string.count('-')
        if ordinal >= len(cls.date_formats):
            raise ValueError('date is not in one of the formats '
                             + ', '.join(cls.date_formats))
        date_format = cls.date_formats[ordinal]
        date = datetime.strptime(string, date_format)
        precision = cls.precisions[ordinal]
        return cls(date, precision)

    def open_right_endpoint(self):
        """Based on the precision, convert the period to a precise
        `datetime` for use as a right endpoint in a right-open interval.
        """
        precision = self.precision
        date = self.date
        if 'year' == self.precision:
            return date.replace(year=date.year + 1, month=1)
        elif 'month' == precision:
            if (date.month < 12):
                return date.replace(month=date.month + 1)
            else:
                return date.replace(year=date.year + 1, month=1)
        elif 'day' == precision:
            return date + timedelta(days=1)
        else:
            raise ValueError('unhandled precision ' + str(precision))


class DateInterval(object):
    """A closed-open interval of dates.

    A left endpoint of None means since the beginning of time.
    A right endpoint of None means towards infinity.
    """

    def __init__(self, start, end):
        if start is not None and end is not None and not start < end:
            raise ValueError("start date {0} is not before end date {1}"
                             .format(start, end))
        self.start = start
        self.end = end

    @classmethod
    def from_periods(cls, start, end):
        """Create an interval with two Periods as the endpoints.
        """
        end_date = end.open_right_endpoint() if end is not None else None
        start_date = start.date if start is not None else None
        return cls(start_date, end_date)

    def contains(self, date):
        if self.start is not None and date < self.start:
            return False
        if self.end is not None and date >= self.end:
            return False
        return True

    def __str__(self):
        return'[{0}, {1})'.format(self.start, self.end)


class DateQuery(FieldQuery):
    """Matches date fields stored as seconds since Unix epoch time.

    Dates can be specified as ``year-month-day`` strings where only year
    is mandatory.

    The value of a date field can be matched against a date interval by
    using an ellipsis interval syntax similar to that of NumericQuery.
    """
    def __init__(self, field, pattern, fast=True):
        super(DateQuery, self).__init__(field, pattern, fast)
        start, end = _parse_periods(pattern)
        self.interval = DateInterval.from_periods(start, end)

    def match(self, item):
        timestamp = float(item[self.field])
        date = datetime.utcfromtimestamp(timestamp)
        return self.interval.contains(date)

    _clause_tmpl = "{0} {1} ?"

    def col_clause(self):
        clause_parts = []
        subvals = []

        if self.interval.start:
            clause_parts.append(self._clause_tmpl.format(self.field, ">="))
            subvals.append(_to_epoch_time(self.interval.start))

        if self.interval.end:
            clause_parts.append(self._clause_tmpl.format(self.field, "<"))
            subvals.append(_to_epoch_time(self.interval.end))

        if clause_parts:
            # One- or two-sided interval.
            clause = ' AND '.join(clause_parts)
        else:
            # Match any date.
            clause = '1'
        return clause, subvals


class Sort(object):
    """An abstract class representing a sort opertation for a query into the
    item database.
    """
    def select_clause(self):
        """ Generates a select sql fragment.
        """
        return None

    def union_clause(self):
        """ Generates a union sql fragment or None if the Sort is a slow sort.
        """
        return None

    def order_clause(self):
        """Generates a sql fragment to be use in a ORDER BY clause
        or None if it's a slow query
        """
        return None

    def sort(self, items):
        """Sort the given items list. Meant to be used with slow queries.
        """
        return items


class MultipleSort(Sort):
    """ Sort class that combines several sort criteria.
    """

    def __init__(self):
        self.sorts = []

    def add_criteria(self, sort):
        self.sorts.append(sort)

    def select_clause(self):
        """ Generate a select sql fragment.
        """
        select_strings = []
        index = 0
        for sort in self.sorts:
            select = sort.select_clause()
            if select is None:
                # FIXME : sort for slow sort
                break
            else:
                select_strings.append(select)
                index = index + 1

        select_string = ",".join(select_strings)
        return "" if not select_string else ", " + select_string

    def union_clause(self):
        """ Returns a union sql fragment.
        """
        union_strings = []
        for sort in self.sorts:
            union = sort.union_clause()
            if union is None:
                pass
            else:
                union_strings.append(union)

        return "".join(union_strings)

    def order_clause(self):
        """Returns a sql fragment to be use in a ORDER BY clause
        or None if it's a slow query
        """
        order_strings = []
        index = 0
        for sort in self.sorts:
            order = sort.order_clause()
            if order is None:
                break
            else:
                order_strings.append(order)
                index = index + 1

        return ",".join(order_strings)

    def sort(self, items):
        # FIXME : sort according to criteria following the first slow sort
        return items


class FlexFieldSort(Sort):

    def __init__(self, model_cls, field, is_ascending):
        self.model_cls = model_cls
        self.field = field
        self.is_ascending = is_ascending

    def select_clause(self):
        """ Return a select sql fragment.
        """
        return "sort_flexattr{0!s}.value as flex_{0!s} ".format(self.field)

    def union_clause(self):
        """ Returns an union sql fragment.
        """
        union = ("LEFT JOIN {flextable} as sort_flexattr{index!s} "
                 "ON {table}.id = sort_flexattr{index!s}.entity_id "
                 "AND sort_flexattr{index!s}.key='{flexattr}' ").format(
            flextable=self.model_cls._flex_table,
            table=self.model_cls._table,
            index=self.field, flexattr=self.field)
        return union

    def order_clause(self):
        """ Returns an order sql fragment.
        """
        order = "ASC" if self.is_ascending else "DESC"
        return "flex_{0} {1} ".format(self.field, order)


class FixedFieldSort(Sort):

    def __init__(self, field, is_ascending=True):
        self.field = field
        self.is_ascending = is_ascending

    """ Sort on a fixed field
    """
    def order_clause(self):
        order = "ASC" if self.is_ascending else "DESC"
        return "{0} {1}".format(self.field, order)


class SmartArtistSort(Sort):
    """ Sort Album or Item on artist sort fields, defaulting back on
        artist field if the sort specific field is empty.
    """
    def __init__(self, model_cls, is_ascending=True):
        self.model_cls = model_cls
        self.is_ascending = is_ascending

    def select_clause(self):
        return ""

    def union_clause(self):
        return ""

    def order_clause(self):
        order = "ASC" if self.is_ascending else "DESC"
        if 'albumartist_sort' in self.model_cls._fields:
            exp1 = 'albumartist_sort'
            exp2 = 'albumartist'
        elif 'artist_sort' in self.model_cls_fields:
            exp1 = 'artist_sort'
            exp2 = 'artist'
        else:
            return ""

        order_str = ('(CASE {0} WHEN NULL THEN {1} '
                     'WHEN "" THEN {1} '
                     'ELSE {0} END) {2} ').format(exp1, exp2, order)
        return order_str


special_sorts = {'smartartist': SmartArtistSort}


def build_sql(model_cls, query, sort_order):
    """ Generate a sql statement (and the values that must be injected into it)
    from a query, sort and a model class.
    """
    where, subvals = query.clause()

    if not sort_order:
        sort_select = ""
        sort_union = ""
        sort_order = ""
    elif isinstance(sort_order, basestring):
        sort_select = ""
        sort_union = ""
        sort_order = " ORDER BY {0}".format(sort_order)
    elif isinstance(sort_order, Sort):
        sort_select = sort_order.select_clause()
        sort_union = sort_order.union_clause()
        sort_order = " ORDER BY {0}".format(sort_order.order_clause())

    sql = ("SELECT {table}.* {sort_select} FROM {table} {sort_union} WHERE "
           "{query_clause} {sort_order}").format(
        sort_select=sort_select,
        sort_union=sort_union,
        table=model_cls._table,
        query_clause=where or '1',
        sort_order=sort_order
    )

    return (sql, subvals, where is None) 