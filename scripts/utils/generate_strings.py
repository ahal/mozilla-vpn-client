#! /usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import yaml
import argparse
import xml.etree.ElementTree as etree
import re

def stop(string_id):
    exit(
        f"Each key must be a string or a list with 1 or more items. Fix string ID `{string_id}`"
    )


def pascalize(string):
    output = ""
    for chunk in string.split("_"):
        output += chunk[0].upper()
        output += chunk[1:]
    return output


# special loader with duplicate key checking
# From: https://gist.github.com/pypt/94d747fe5180851196eb
class UniqueKeyLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        mapping = []
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in mapping:
                print(f"Warning!! {key} is duplicated!")
            assert key not in mapping
            mapping.append(key)
        return super().construct_mapping(node, deep)


def parseXLIFFTranslationStrings(xliff_file):
    if not os.path.isfile(xliff_file):
        exit(f"Unable to find {xliff_file}")

    strings = {}

    tree = etree.parse(xliff_file)
    root = tree.getroot()

    for node in root.findall('.//{urn:oasis:names:tc:xliff:document:1.2}trans-unit'):
        # Remove any unexpected characters e.g. São Paulo -> SoPaulo
        id = re.sub(r'[^a-zA-Z._]', '', node.get('id'))
        cpp_id = pascalize(id.replace('.', '_'))
        value = node.findall('.//{urn:oasis:names:tc:xliff:document:1.2}source')[0].text

        strings[cpp_id] = {
            "string_id": id,
            "value": [value],
            "comments": [],
        }

    return strings


def parseYAMLTranslationStrings(yamlfile):
    if not os.path.isfile(yamlfile):
        exit(f"Unable to find {yamlfile}")

    yaml_strings = {}
    with open(yamlfile, "r", encoding="utf-8") as yaml_file:
        # Enforce a new line at the end of the file
        last_line = yaml_file.readlines()[-1]
        if last_line == last_line.rstrip():
            exit("The yaml file must have an empty line at the end")

        # Reset position after reading the whole content
        yaml_file.seek(0)
        yaml_content = yaml.load(yaml_file, UniqueKeyLoader)
        if yaml_content is None:
            return yaml_strings

        if type(yaml_content) is not dict:
            exit(f"The {yamlfile} file must contain collections only")

        for category in yaml_content:
            for key in yaml_content[category]:
                string_id = f"vpn.{category}.{key}"
                obj = yaml_content[category][key]
                value = []
                comments = []

                if type(obj) is str:
                    if len(obj) == 0:
                        stop(string_id)
                    value = [obj]

                elif type(obj) is dict:
                    if not ("value" in obj):
                        exit(
                            f"The key {string_id} must contain a `value` string or an array of strings"
                        )

                    if type(obj["value"]) is str:
                        value = [obj["value"]]

                    elif type(obj["value"]) is list:
                        for x in range(0, len(obj["value"])):
                            value.append(obj["value"][x])

                    else:
                        exit(
                            f"The value of {string_id} must be a string or an array of strings"
                        )

                    if "comment" in obj:
                        if type(obj["comment"]) is str:
                            comments = [obj["comment"]]

                        elif type(obj["comment"]) is list:
                            for x in range(0, len(obj["comment"])):
                                comments.append(obj["comment"][x])

                        else:
                            exit(
                                f"The comment of {string_id} must be a string or an array of strings"
                            )

                    if len(value) == 0:
                        stop(string_id)

                else:
                    stop(string_id)

                yaml_strings[pascalize(f"{category}_{key}")] = {
                    "string_id": string_id,
                    "value": value,
                    "comments": comments,
                }

        return yaml_strings


# Render a dictionary of strings into the i18nstrings module.
def generateStrings(strings, outdir):
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "i18nstrings.h"), "w", encoding="utf-8") as output:
        output.write(
            """/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

// AUTOGENERATED! DO NOT EDIT!!

#ifndef I18NSTRINGS_H
#define I18NSTRINGS_H

#include <QQmlPropertyMap>

class I18nStrings final : public QQmlPropertyMap {
  Q_OBJECT
  Q_DISABLE_COPY_MOVE(I18nStrings)

 public:
  enum String {
    Empty,
"""
        )

        for key in strings:
            output.write(f"    {key},\n")

        output.write(
            """    __Last,
  };

  static String getString(const QString& s) {
    return s_stringIdMap.value(s, I18nStrings::Empty);
  }

  static I18nStrings* instance();
  static void initialize();

  explicit I18nStrings(QObject* parent);
  ~I18nStrings() = default;

  void retranslate();

  const char* id(I18nStrings::String) const;

  QString t(I18nStrings::String) const;

 private:
  static const char* const _ids[];

  static inline const QHash<QString, I18nStrings::String> s_stringIdMap = {
"""
    )

        for i, key in enumerate(strings):
            output.write(f"    {{\"{key}\", I18nStrings::{key}}}, \n")

        output.write("""
  };
};

#endif  // I18NSTRINGS_H
"""
        )

    with open(
        os.path.join(outdir, "i18nstrings_p.cpp"), "w", encoding="utf-8"
    ) as output:
        output.write(
            """/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

// AUTOGENERATED! DO NOT EDIT!!

#include "i18nstrings.h"

// static
const char* const I18nStrings::_ids[] = {
    // The first ID is for the empty string.
    "",

"""
        )

        def serialize(string):
            ret = "\\n".join(string)
            return ret.replace('"', '\\"')

        for key, data in strings.items():
            output.write(f"    //% \"{serialize(data['value'])}\"\n")
            for comment in data["comments"]:
                output.write(f"    //: {comment}\n")
            output.write(f"    QT_TRID_NOOP(\"{data['string_id']}\"),\n\n")

        # This is done to make windows compiler happy
        if len(strings) == 0:
            output.write(f'    "dummy.ignore",\n\n')

        output.write(
            """
};

"""
        )

        # Generate the retranslate() method.
        output.write("void I18nStrings::retranslate() {\n")
        for key in strings:
            output.write(f'    insert("{key}", qtTrId(_ids[{key}]));\n')
        output.write("}")


if __name__ == "__main__":
    # Parse arguments to locate the input and output files.
    parser = argparse.ArgumentParser(
        description="Generate internationalization strings database from a YAML and/or XLIFF sources"
    )
    parser.add_argument(
        "sources",
        metavar="SOURCE",
        type=str,
        action="store",
        nargs='+',
        help="Comma separated list of YAML and/or XLIFF sources to parse",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="DIR",
        type=str,
        action="store",
        help="Output directory for generated files",
    )
    args = parser.parse_args()

    if not args.sources:
        exit("No source argument.")

    # If no output directory was provided, use the current directory.
    if args.output is None:
        args.output = os.getcwd()

    # Parse the inputs
    strings = {}
    for source in args.sources:
        _, ext = os.path.splitext(source)
        if ext == '.yaml':
            substrings = parseYAMLTranslationStrings(source)
            strings.update(substrings)
        elif ext == '.xliff':
            substrings = parseXLIFFTranslationStrings(source)
            strings.update(substrings)
        else:
            raise f'Unknown file format provided: {source}'

    # Render the strings into generated content.
    generateStrings(strings, args.output)
