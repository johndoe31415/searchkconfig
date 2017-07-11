#	searchkconfig - Search Linux kernel KConfig files.
#	Copyright (C) 2017-2017 Johannes Bauer
#
#	This file is part of searchkconfig.
#
#	searchkconfig is free software; you can redistribute it and/or modify
#	it under the terms of the GNU General Public License as published by
#	the Free Software Foundation; this program is ONLY licensed under
#	version 3 of the License, later versions are explicitly excluded.
#
#	searchkconfig is distributed in the hope that it will be useful,
#	but WITHOUT ANY WARRANTY; without even the implied warranty of
#	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#	GNU General Public License for more details.
#
#	You should have received a copy of the GNU General Public License
#	along with searchkconfig; if not, write to the Free Software
#	Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
#	Johannes Bauer <JohannesBauer@gmx.de>
#

import os
import re
import collections
import tpg

import Tools
from KConfigParser import KConfigParser
from KConfigObjects import Symbol, Source, ConfigurationItem, Menu, ConfigType, Option, DefaultValue, DependsOn, Select, DefType, Conditional, Range, Comment, Imply, VisibleIf
from KernelConfiguration import KernelConfiguration, ConfigOptionState

class ConfigOption(object):
	def __init__(self, filename, lineno, symbol_name):
		self._origin_filename = filename
		self._origin_lineno = lineno
		self._symbol = symbol_name
		self._otype = None
		self._otext = None
		self._helptext = ""
		self._conditions = [ ]

	def add_helptext_line(self, line):
		self._helptext += line + "\n"

	def set_type_text(self, otype, otext):
		self._otype = otype
		self._otext = otext

	def matches(self, search_spec):
		if (not search_spec.include_unnamed) and (self._otext is None):
			return False

		if search_spec.regex is not None:
			result = None
			result = result or search_spec.regex.search(self._symbol.name)
			if self._otext is not None:
				result = result or search_spec.regex.search(self._otext)
			return result is not None
		else:
			return True

	def _format_help(self, prefix):
		for line in self._helptext.strip().split("\n"):
			yield (prefix + line).rstrip()

	def append_condition(self, condition):
		self._conditions.append(condition)

	def append_all_conditions(self, conditions):
		self._conditions += conditions

	def format_help(self, prefix = ""):
		return "\n".join(self._format_help(prefix))

	def format(self, dump_spec = None):
		if self._otext is None:
			text = self._symbol
		else:
			text = "%s (%s)" % (self._otext, self._symbol)

		text = self._symbol.get_colorizer(dump_spec.kconfig)(text)

#		if dump_spec.kconfig is not None:
#			if dump_spec.kconfig[self._symbol]:
#				text += " enabled"
#			else:
#				text += " disabled"

		if (dump_spec is not None) and (dump_spec.show_origin):
			text += " {%s:%d}" % (self._origin_filename, self._origin_lineno)
		if (dump_spec is not None) and (dump_spec.show_conditions):
			if len(self._conditions) > 0:
				text += " if "
				text += " and ".join(condition.format(dump_spec.kconfig) for condition in self._conditions)
		return text

	def __str__(self):
		return self.format()

class ConfigMenu(object):
	def __init__(self, text, multiple_choice = False, parent = None):
		self._multiple_choice = multiple_choice
		self._text = text
		self._submenus = [ ]
		self._parent = parent
		self._options = [ ]

	@property
	def text(self):
		return self._text

	def add_helptext_line(self, line):
		pass

	def set_type_text(self, otype, otext):
		assert(self._multiple_choice)
		self._text = "{" + otext + "}"

	@property
	def current_option(self):
		if self._multiple_choice and (len(self._options) == 0):
			return self
		else:
			return self._options[-1]

	def add_option(self, option):
		self._options.append(option)
		return option

	def search(self, search_spec):
		matching_options = [ option for option in self._options if option.matches(search_spec) ]
		matching_submenus = [ submenu.search(search_spec) for submenu in self._submenus ]
		matching_submenus = [ submenu for submenu in matching_submenus if (submenu is not None) ]
		match_count = len(matching_options) + len(matching_submenus)
		if match_count == 0:
			return None
		else:
			result = ConfigMenu(self._text, self._parent)
			for option in matching_options:
				result.add_option(option)
			for submenu in matching_submenus:
				result.add_submenu(submenu)
			return result

	def dump(self, dump_spec, indent = 0):
		indent_str = "    " * indent
		print(indent_str + self.text)
		for option in self._options:
			print(indent_str + "  * " + option.format(dump_spec))
			if dump_spec.show_help:
				print(option.format_help(indent_str + "    "))
		for submenu in self._submenus:
			submenu.dump(dump_spec, indent + 1)

	def leave_submenu(self):
		return self._parent

	def add_submenu(self, submenu):
		submenu._parent = self
		self._submenus.append(submenu)
		return submenu

class KConfigFileParser(object):
	_INDENT_RE = re.compile("(?P<indent>^[ \t]*).*")

	def __init__(self, basedir, filename, replacements = None):
		self._basedir = basedir
		self._filename = filename
		if replacements is None:
			self._replacements = { }
		else:
			self._replacements = replacements
		self._helptext = False
		self._helpindent = None
		self._configparse = KConfigParser()
		self._parse_result = None
		self._current_menu = None
		self._conditions = [ ]

	def _replace_all(self, text):
		for (src, dst) in self._replacements.items():
			text = text.replace(src, dst)
		return text

	def _add_helptext_line(self, filename, lineno, line = ""):
		line = Tools.expand_tabs(line)[self._helpindent : ]
		self._current_menu.current_option.add_helptext_line(line)

	def _parse_line(self, filename, lineno, line):
		strippedline = line.strip()
		if strippedline.startswith("#"):
			return

		if self._helptext:
			if len(strippedline) == 0:
				self._add_helptext_line(filename, lineno)
				return
			indent = self._INDENT_RE.match(line).groupdict()["indent"]
			indent_level = Tools.apparent_length(indent, tabsize = 8)
			if self._helpindent is None:
				# First help line, the specifies the indent. Unless indent is
				# zero, then we have no help text, but (annoyingly) an
				# "---help---" marker.
				if indent_level > 0:
					self._helpindent = indent_level
					self._add_helptext_line(filename, lineno, line)
				else:
					self._helptext = False
					self._helpindent = None
			else:
				if indent_level < self._helpindent:
					# We're not in help text anymore
					self._helptext = False
					self._helpindent = None
				else:
					# Continue help text
					self._add_helptext_line(filename, lineno, line)


		if not self._helptext:
			splitline = strippedline.split(maxsplit = 1)
			if len(splitline) == 0:
				return
			keyword = splitline[0]
			arguments = splitline[1:]

			if keyword in [ "help", "---help---" ]:
				self._helptext = True
			else:
				if keyword in [ "choice", "endchoice", "endmenu", "endif", "optional" ]:
					if keyword in [ "endmenu", "endchoice" ]:
						self._current_menu = self._current_menu.leave_submenu()
					elif keyword == "choice":
						self._current_menu = self._current_menu.add_submenu(ConfigMenu("Multiple choices", multiple_choice = True))
					elif keyword == "endif":
						self._conditions.pop()
				else:
					try:
						result = self._configparse.parse("ConfigurationItem", line)
					except tpg.SyntacticError as e:
						exception = e
						result = None
					if result is None:
						raise Exception("Parse error of %s/%s:%d \"%s\": %s" % (self._basedir, self._filename, lineno, line, exception))

					if isinstance(result, Menu):
						self._current_menu = self._current_menu.add_submenu(ConfigMenu(result.text))
					elif isinstance(result, ConfigurationItem):
						print(result)
						option = self._current_menu.add_option(ConfigOption(filename, lineno, result.symbol))
						option.append_all_conditions(self._conditions)
					elif isinstance(result, ConfigType):
						self._current_menu.current_option.set_type_text(result.typename, result.text)
					elif isinstance(result, Option):
						pass
					elif isinstance(result, DefaultValue):
						pass
					elif isinstance(result, DependsOn):
						pass
					elif isinstance(result, Select):
						pass
					elif isinstance(result, Range):
						pass
					elif isinstance(result, DefType):
						pass
					elif isinstance(result, Comment):
						pass
					elif isinstance(result, VisibleIf):
						pass
						#self._current_menu.current_option.append_option(result.condition)
					elif isinstance(result, Imply):
						pass
					elif isinstance(result, Conditional):
						self._conditions.append(result.condition)
					elif isinstance(result, Source):
						filename = self._replace_all(result.filename)
						self._parse(filename)
					else:
						raise Exception("Parser returned unknown object: %s for %s" % (str(result), line))

	def _parse(self, filename):
		with open(self._basedir + "/" + filename) as f:
			continued_line = ""
			for (lineno, line) in enumerate(f, 1):
				line = line.rstrip("\r\n")
				if line.endswith("\\"):
					# Continuation
					continued_line += line[:-1]
				else:
					self._parse_line(filename, lineno, continued_line + line)
					continued_line = ""

	def parse(self):
		self._parse_result = ConfigMenu(self._filename)
		self._current_menu = self._parse_result
		self._parse(self._filename)
		return self._parse_result


class KConfigScanner(object):
	_SearchSpec = collections.namedtuple("SearchSpec", [ "regex", "include_unnamed" ])
	_DumpSpec = collections.namedtuple("DumpSpec", [ "show_origin", "show_help", "show_conditions", "kconfig" ])

	def __init__(self, args):
		self._args = args
		self._basedir = os.path.realpath(self._args.kernel_path) + "/"
		if self._args.kernel_config is not None:
			self._kconfig = KernelConfiguration(self._args.kernel_config)
		else:
			self._kconfig = None

	def scan(self):
		variables = {
			"$SRCARCH":		self._args.arch,
		}
		self._root = KConfigFileParser(self._basedir, self._args.startfile, variables).parse()
		if self._args.search is None:
			search_spec = self._SearchSpec(regex = None, include_unnamed = self._args.include_unnamed)
		else:
			regex = re.compile(self._args.search, flags = 0 if self._args.no_ignore_case else re.IGNORECASE)
			search_spec = self._SearchSpec(regex = regex, include_unnamed = self._args.include_unnamed)
		result = self._root.search(search_spec)

		if result is None:
			print("Sorry, no search results that matched your criteria.")
		else:
			dump_spec = self._DumpSpec(show_origin = self._args.show_origin, show_help = self._args.show_help, show_conditions = self._args.show_conditions, kconfig = self._kconfig)
			result.dump(dump_spec)

