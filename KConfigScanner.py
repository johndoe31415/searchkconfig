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
import enum
import sys

import Tools
from KConfigParser import KConfigParser
from KConfigObjects import Symbol, Source, ConfigurationItem, Menu, ConfigType, Option, DefaultValue, DependsOn, Select, DefType, Conditional, Range, Comment, Imply, VisibleIf
from KernelConfiguration import KernelConfiguration, ConfigOptionState

class ItemType(enum.IntEnum):
	RootMenu = 0
	SubMenu = 1
	Config = 2
	MenuConfig = 3
	Choice = 4

class ConfigItem(object):
	def __init__(self, itemtype, parent = None, text = None, symbol = None):
		self._itemtype = itemtype
		self._parent = parent
		self._text = text
		self._symbol = symbol
		self._helppage = None
		self._children = [ ]

	@property
	def itemtype(self):
		return self._itemtype

	@property
	def parent(self):
		return self._parent

	@property
	def text(self):
		return self._text

	@text.setter
	def text(self, value):
		assert(value is not None)
		self._text = value

	@property
	def symbol(self):
		return self._symbol

	def add_helptext_line(self, line):
		pass

	def matches(self, search_spec):
		if self.symbol is None:
			return False

		if (not search_spec.include_unnamed) and (self.text is None):
			return False

		if search_spec.regex is not None:
			result = None
			result = result or search_spec.regex.search(self.symbol.name)
			if self.text is not None:
				result = result or search_spec.regex.search(self.text)
			return result is not None
		else:
			return True

	def search(self, search_spec):
		if self.matches(search_spec):
			yield self
		for child in self._children:
			yield from child.search(search_spec)

	def dump(self, dump_spec = None, indent = 0):
		indent_str = "    " * indent
		print("%s%s %s" % (indent_str, self.text, self.symbol))
#		for chilon in self._options:
#			print(indent_str + "  * " + option.format(dump_spec))
#			if (dump_spec is not None) and (dump_spec.show_help):
#				print(option.format_help(indent_str + "    "))
		for child in self._children:
			child.dump(dump_spec, indent + 1)

	def add_item(self, item):
		item._parent = self
		self._children.append(item)
		return item

	def __str__(self):
		return "ConfigItem<%s, %s, %s, parent = %s>" % (self.itemtype.name, self.symbol, self.text, self.parent)

class KConfigFileParser(object):
	_INDENT_RE = re.compile("(?P<indent>^[ \t]*).*")

	def __init__(self, basedir, filename, replacements = None):
		self._basedir = basedir
		if not self._basedir.endswith("/"):
			self._basedir += "/"
		self._filename = filename
		if replacements is None:
			self._replacements = { }
		else:
			self._replacements = replacements
		self._helptext = False
		self._helpindent = None
		self._configparse = KConfigParser()
		self._parse_result = None
		self._current_item = None
		self._current_menu = None
		self._conditions = [ ]
		self._menuconfig_symbols = [ ]

	def _add_item(self, item):
		self._current_item = self._current_menu.add_item(item)

	def _enter_submenu(self, item):
		self._current_menu = self._current_menu.add_item(item)
		self._current_item = self._current_menu

	def _leave_submenu(self):
		self._current_menu = self._current_menu.parent
		self._current_item = self._current_menu

	def _replace_all(self, text):
		for (src, dst) in self._replacements.items():
			text = text.replace(src, dst)
		return text

	def _add_helptext_line(self, filename, lineno, line = ""):
		line = Tools.expand_tabs(line)[self._helpindent : ]
		self._current_item.add_helptext_line(line)

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
						self._leave_submenu()
					elif keyword == "choice":
						self._enter_submenu(ConfigItem(ItemType.Choice))
					elif keyword == "endif":
						self._conditions.pop()
				else:
					try:
						result = self._configparse.parse("ConfigurationItem", line)
					except tpg.SyntacticError as e:
						exception = e
						result = None
					if result is None:
						raise Exception("Parse error of %s%s:%d \"%s\": %s" % (self._basedir, self._filename, lineno, line, exception))

					if isinstance(result, Menu):
						self._enter_submenu(ConfigItem(ItemType.SubMenu, text = result.text))
					elif isinstance(result, ConfigurationItem):
#						conditionset = set(condition.name for condition in self._conditions if isinstance(condition, Symbol))
#						while len(self._menuconfig_symbols) > 0:
#							if self._menuconfig_symbols[-1] not in conditionset:
#								self._menuconfig_symbols.pop()
#								self._current_menuitem = self._current_menuitem.leave_submenu()
#							else:
#								break

#						if result.conftype == "menuconfig":
#							self._current_menuitem = self._current_menuitem.add_submenu(ConfigMenu(result.symbol.name + " -->"))
#							self._menuconfig_symbols.append(result.symbol.name)
						if result.conftype == "menuconfig":
							itemtype = ItemType.MenuConfig
						else:
							itemtype = ItemType.Config
						self._add_item(ConfigItem(itemtype, symbol = result.symbol))
#						option.append_all_conditions(self._conditions)
					elif isinstance(result, ConfigType):
						if result.text is not None:
							self._current_item.text = result.text
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
						#self._current_menuitem.current_option.append_option(result.condition)
					elif isinstance(result, Imply):
						pass
					elif isinstance(result, Conditional):
						self._conditions.append(result.condition)
					elif isinstance(result, Source):
						filename = self._replace_all(result.filename)
						self._parse_file(filename)
					else:
						raise Exception("Parser returned unknown object: %s for %s" % (str(result), line))

	def _parse_file(self, filename):
		self._parse_stack.append([ filename, 0 ])
		with open(self._basedir + filename) as f:
			continued_line = ""
			for (lineno, line) in enumerate(f, 1):
				line = line.rstrip("\r\n")
				if line.endswith("\\"):
					# Continuation
					continued_line += line[:-1]
				else:
					self._parse_stack[-1][1] = lineno
					self._parse_line(filename, lineno, continued_line + line)
					continued_line = ""
		self._parse_stack.pop()

	def _parse(self):
		self._parse_stack = [ ]
		self._parse_result = ConfigItem(ItemType.RootMenu, text = self._filename)
		self._current_menu = self._parse_result
		self._current_item = self._parse_result
		self._parse_file(self._filename)
		return self._parse_result

	def parse(self):
		try:
			return self._parse()
		except (IndexError, AssertionError) as e:
			print("Parsing error:")
			for (filename, lineno) in reversed(self._parse_stack):
				print("    %s%s line %d" % (self._basedir, filename, lineno))
			print()
			print("Caused %s" % (e))
			sys.exit(1)


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
		self._root.dump()
		if self._args.search is None:
			search_spec = self._SearchSpec(regex = None, include_unnamed = self._args.include_unnamed)
		else:
			regex = re.compile(self._args.search, flags = 0 if self._args.no_ignore_case else re.IGNORECASE)
			search_spec = self._SearchSpec(regex = regex, include_unnamed = self._args.include_unnamed)
		result = list(self._root.search(search_spec))

		if result is None:
			print("Sorry, no search results that matched your criteria.")
		else:
			dump_spec = self._DumpSpec(show_origin = self._args.show_origin, show_help = self._args.show_help, show_conditions = self._args.show_conditions, kconfig = self._kconfig)
			result.dump(dump_spec)

