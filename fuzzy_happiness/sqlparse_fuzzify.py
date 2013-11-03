#!/usr/bin/python

import datetime
import re
import sqlparse
import sys

#import attributes


TABLE_NAME_RE = re.compile('CREATE TABLE `(.+)`')
COLUMN_RE = re.compile('  `(.+)` ([^ ,]+).*')


class DumpProcessor(object):
    def __init__(self, input_path, output_path, anon_fields):
        self.input_path = input_path
        self.output_path = output_path
        self.anon_fields = anon_fields

    def read_sql_dump(self):
        # Read blocks, separating by blank lines. Each block is parsed as a
        # group.
        with open(self.input_path) as f:
            with open(self.output_path, 'w') as self.out:
                pre_insert = []
                inserts = []
                post_insert = []

                l = f.readline()
                while l:
                    if not l.startswith('-- Table structure for'):
                        if l.startswith('INSERT'):
                            inserts.append(l)
                        elif not inserts:
                            pre_insert.append(l)
                        else:
                            post_insert.append(l)
                    else:
                        post_insert.append(l)
                        self.parse_block(''.join(pre_insert), inserts,
                                         ''.join(post_insert))
                        pre_insert = []
                        inserts = []
                        post_insert = []

                    l = f.readline()

                if pre_insert or inserts or post_insert:
                    self.parse_block(''.join(pre_insert), inserts,
                                     ''.join(post_insert))

    def parse_block(self, pre_insert, inserts, post_insert):
        # Special case empty tables
        if not inserts:
            self.out.write(pre_insert)
            self.out.write(''.join(inserts))
            self.out.write(post_insert)
            return

        self.out.write(pre_insert)
        create_statement = self.extract_create(pre_insert)
        if not create_statement and inserts:
            print 'Error! How can we have inserts without a create?'
            print 'PRE %s' % pre_insert
            for insert in inserts:
                print 'INS %s' % insert
            print 'PST %s' % post_insert
            sys.exit(1)

        if create_statement:
            table_name, columns = self.parse_create(create_statement)

        for insert in inserts:
            self.out.write(insert)

        self.out.write(post_insert)

    def extract_create(self, pre_insert):
        # This method is over engineered. If we're just looking for creates we
        # could just filter this more aggressively. However, I wanted to
        # understand what the other tokens were before I did that, and now I
        # have all this code...
        create_data = []

        ignore_statement = False
        create_statement = False
        for parse in sqlparse.parse(pre_insert):
            for token in parse.tokens:
                # End of statement
                if token.value in [';']:
                    ignore_statement = False
                    create_statement = False
                    continue

                # If we've decided to ignore this entire statement, then do
                # that
                if ignore_statement:
                    continue

                if token.is_whitespace():
                    continue

                # Capture create details
                if create_statement:
                    create_data.append(token.value)
                    continue

                # Filter out boring things
                if isinstance(token, sqlparse.sql.Comment):
                    continue
                if str(token.ttype) in ['Token.Comment.Single']:
                    continue
                if token.value in ['LOCK', 'UNLOCK']:
                    ignore_statement = True
                    continue

                # DDL is special
                if str(token.ttype) == 'Token.Keyword.DDL':
                    if token.value == 'DROP':
                        ignore_statement = True
                        continue
                    if token.value == 'CREATE':
                        create_data.append(token.value)
                        create_statement = True
                        continue

                print 'Unknown parser token!'
                print token
                print dir(token)
                print 'ttype: %s = >>%s<<' % (str(token.ttype), token.value)
                print '    %s: %s' % (type(token), repr(token))

        return ' '.join(create_data)

    def parse_create(self, create_statement):
        # sqlparse falls apart when you ask it to parse DDL. It thinks that
        # the DDL statement is a function, and doesn't quite know what to do.
        # So, we're going to revert to something more basic for creates.
        table_name = None
        columns = {}

        for line in create_statement.split('\n'):
            print line
            m = TABLE_NAME_RE.match(line)
            if m:
                table_name = m.group(1)

            m = COLUMN_RE.match(line)
            if m:
                columns[m.group(1)] = m.group(2)

        return table_name, columns


if __name__ == '__main__':
    #anon_fields = attributes.load_configuration()

    anon_fields = {}
    dp = DumpProcessor('/home/mikal/datasets/nova_user_001.sql',
                       '/tmp/nova_user_001.sql.post',
                       anon_fields)
    dp.read_sql_dump()
