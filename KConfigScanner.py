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
	_KEY_ABBREVIATION_RE = re.compile("([abcdefghijklopqrstuvwxz])", re.IGNORECASE)
	def __init__(self, itemtype, parent = None, text = None, symbol = None, filename = None, lineno = None, conditions = None):
		self._itemtype = itemtype
		self._parent = parent
		self._text = text
		self._symbol = symbol
		self._origin_filename = filename
		self._origin_lineno = lineno
		self._helptext = None
		self._children = [ ]
		self._visible = False
		self._conditions = [ ]
		if conditions is not None:
			self.append_all_conditions(conditions)

	@property
	def abbreviation_key(self):
		if (self.text is None) or (self.itemtype == ItemType.RootMenu):
			return None
		result = self._KEY_ABBREVIATION_RE.search(self.text.value)
		if result is None:
			return None
		else:
			return result.group(0).lower()

	@property
	def visible(self):
		return self._visible

	@visible.setter
	def visible(self, value):
		self._visible = value

	def set_visible(self):
		node = self
		while node is not None:
			node.visible = True
			node = node.parent

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

	def append_condition(self, condition):
		self._conditions.append(condition)

	def append_all_conditions(self, conditions):
		self._conditions += conditions

	def add_helptext_line(self, line):
		line = line.strip()
		if self._helptext is None:
			self._helptext = [ line ]
		else:
			self._helptext.append(line)

	def matches(self, search_spec):
		if self.symbol is None:
			return False

		if (not search_spec.include_unnamed) and (self.text is None):
			return False

		if search_spec.regex is not None:
			result = None
			result = result or search_spec.regex.search(self.symbol.name)
			if self.text is not None:
				result = result or search_spec.regex.search(self.text.value)
			return result is not None
		else:
			return True

	def searchlist(self, search_spec):
		if self.matches(search_spec):
			yield self
		for child in self._children:
			yield from child.searchlist(search_spec)

	def enable_visibility(self, search_spec):
		count = 0
		for leafnode in self.searchlist(search_spec):
			leafnode.set_visible()
			count += 1
		return count

	@property
	def have_help(self):
		return (self._helptext is not None) and (len(Tools.striplist(self._helptext)) > 0)

	def format_help(self, prefix = ""):
		helptext = Tools.striplist(self._helptext)
		return prefix + ("\n" + prefix).join(helptext)

	def format(self, dump_spec = None):
		if self.text is None:
			text = self.symbol
		else:
			if self.symbol is not None:
				text = "%s (%s)" % (self.text, self.symbol)
			else:
				text = self.text

		if self.symbol is not None:
			text = self.symbol.get_colorizer(dump_spec.kconfig)(text)

		if (dump_spec is not None) and (dump_spec.show_key):
			key = self.abbreviation_key
			if key is not None:
				text = "(%s) %s" % (key, text)

		if (dump_spec is not None) and (dump_spec.show_origin):
			text += " {%s:%d}" % (self._origin_filename, self._origin_lineno)
		if (dump_spec is not None) and (dump_spec.show_conditions):
			if len(self._conditions) > 0:
				text += " if "
				text += " and ".join(condition.format(dump_spec.kconfig) for condition in self._conditions)
		return text

	def dump(self, dump_spec = None, indent = 0):
		if not self.visible:
			return
		indent_str = "    " * indent
		print("%s%s" % (indent_str, self.format(dump_spec)))
		if (dump_spec is not None) and (dump_spec.show_help) and self.have_help:
			print(self.format_help(indent_str + "    "))
		for child in self._children:
			child.dump(dump_spec, indent + 1)

	def add_item(self, item):
		item._parent = self
		self._children.append(item)
		return item

	def _could_be_child_of(self, potential_parent):
		return (potential_parent is not None) and (potential_parent.symbol is not None) and any(condition.requires(potential_parent.symbol) for condition in self._conditions)

	def _reparent(self, new_parent, new_children):
		if new_parent is None:
			return
#		if len(new_children):
#			print("Reparenting %d children to %s" % (len(new_children), new_parent))
		for child in new_children:
			new_parent.add_item(child)

	def create_submenus(self):
		potential_parent = None
		potential_children = [ ]
		remaining_children = [ ]
		for child in self._children:
			if child._could_be_child_of(potential_parent):
				# Continuation of current submenu
				potential_children.append(child)
			elif (child.itemtype in [ ItemType.Config, ItemType.MenuConfig]):
				# Potential start of submenu
				self._reparent(potential_parent, potential_children)
				potential_parent = child
				potential_children = [ ]
				remaining_children.append(child)
			else:
				# Just regular old additional item
				self._reparent(potential_parent, potential_children)
				potential_parent = None
				potential_children = [ ]
				remaining_children.append(child)

		self._reparent(potential_parent, potential_children)
		self._children = remaining_children

		for child in self._children:
			child.create_submenus()

	def __repr__(self):
		return "ConfigItem<%s, %s, %s, cond = %s>" % (self.itemtype.name, self.symbol, self.text, self._conditions)

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
						self._enter_submenu(ConfigItem(ItemType.Choice, filename = filename, lineno = lineno, conditions = self._conditions))
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
						self._enter_submenu(ConfigItem(ItemType.SubMenu, text = result.text, filename = filename, lineno = lineno, conditions = self._conditions))
					elif isinstance(result, ConfigurationItem):
						if result.conftype == "menuconfig":
							itemtype = ItemType.MenuConfig
						else:
							itemtype = ItemType.Config
						self._add_item(ConfigItem(itemtype, symbol = result.symbol, filename = filename, lineno = lineno, conditions = self._conditions))
					elif isinstance(result, ConfigType):
						if result.text is not None:
							self._current_item.text = result.text
					elif isinstance(result, Option):
						pass
					elif isinstance(result, DefaultValue):
						pass
					elif isinstance(result, DependsOn):
						self._current_item.append_condition(result.dependency)
					elif isinstance(result, Select):
						pass
					elif isinstance(result, Range):
						pass
					elif isinstance(result, DefType):
						pass
					elif isinstance(result, Comment):
						pass
					elif isinstance(result, VisibleIf):
						self._current_item.append_condition(result.condition)
					elif isinstance(result, Imply):
						pass
					elif isinstance(result, Conditional):
						self._conditions.append(result.condition)
					elif isinstance(result, Source):
						filename = self._replace_all(result.filename.value)
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
		self._parse_result = ConfigItem(ItemType.RootMenu, text = self._filename, filename = self._filename, lineno = 0)
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
	_DumpSpec = collections.namedtuple("DumpSpec", [ "show_origin", "show_help", "show_conditions", "show_key", "kconfig" ])

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
		rootnode = KConfigFileParser(self._basedir, self._args.startfile, variables).parse()
		if self._args.search is None:
			search_spec = self._SearchSpec(regex = None, include_unnamed = self._args.include_unnamed)
		else:
			regex = re.compile(self._args.search, flags = 0 if self._args.no_ignore_case else re.IGNORECASE)
			search_spec = self._SearchSpec(regex = regex, include_unnamed = self._args.include_unnamed)
		if not self._args.no_submenus:
			rootnode.create_submenus()
		result = rootnode.enable_visibility(search_spec)

		if result == 0:
			print("Sorry, no search results that matched your criteria.")
		else:
			dump_spec = self._DumpSpec(show_origin = self._args.show_origin, show_help = self._args.show_help, show_conditions = self._args.show_conditions, show_key = True, kconfig = self._kconfig)
			rootnode.dump(dump_spec)

