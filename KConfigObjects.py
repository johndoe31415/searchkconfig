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

import collections
import Tools
from KernelConfiguration import ConfigOptionState

Menu = collections.namedtuple("Menu", [ "menutype", "text" ])
Source = collections.namedtuple("Source", [ "filename" ])
Comment = collections.namedtuple("Comment", [ "text" ])
ConfigType = collections.namedtuple("ConfigType", [ "typename", "text", "condition" ])
DefType = collections.namedtuple("DefType", [ "typename", "value", "condition" ])
Range = collections.namedtuple("Range", [ "fromvalue", "tovalue", "condition" ])
DependsOn = collections.namedtuple("DependsOn", [ "dependency" ])
Option = collections.namedtuple("Option", [ "parameters" ])
DefaultValue = collections.namedtuple("DefaultValue", [ "value", "condition" ])
Select = collections.namedtuple("Select", [ "symbol", "condition" ])
Imply = collections.namedtuple("Imply", [ "symbol", "condition" ])
VisibleIf = collections.namedtuple("VisibleIf", [ "condition" ])
Conditional = collections.namedtuple("Conditional", [ "condition" ])
Comparison = collections.namedtuple("Comparison", [ "lhs", "op", "rhs" ])
ConfigurationItem = collections.namedtuple("ConfigurationItem", [ "conftype", "symbol" ])

class Literal(object):
	def __init__(self, value):
		self._value = value

	@property
	def value(self):
		return self._value

	def requires(self, symbol):
		return False

	def __str__(self):
		return self.value

class Symbol(object):
	def __init__(self, name):
		self._name = name

	@property
	def name(self):
		return self._name

	def requires(self, symbol):
		return symbol == self

	def _get_color(self, kconfig):
		value = kconfig[self.name]
		return {
			ConfigOptionState.Enabled:	"green",
			ConfigOptionState.Disabled:	"red",
			ConfigOptionState.Module:	"cyan",
		}.get(value, "gray")

	def get_colorizer(self, kconfig):
		if kconfig is None:
			return lambda text: text
		else:
			return lambda text: Tools.colorize_text(text, self._get_color(kconfig))

	def format(self, kconfig = None):
		if kconfig is not None:
			color = self._get_color(kconfig)
			return Tools.colorize_text(self.name, color)
		else:
			return self.name

	def _cmpkey(self):
		return ("symbol", self.name)

	def __eq__(self, other):
		return (self.__class__ == other.__class__) and (self._cmpkey() == other._cmpkey())

	def __lt__(self, other):
		return (self.__class__ == other.__class__) and (self._cmpkey() < other._cmpkey())

	def __neq__(self, other):
		return not (self == other)

	def __hash__(self):
		return hash(self._cmpkey())

	def __repr__(self):
		return self._name

class Comparison(object):
	def __init__(self, lhs, op, rhs):
		self._lhs = lhs
		self._op = op
		self._rhs = rhs

	def requires(self, symbol):
		if self._op == "&&":
			return self._lhs.requires(symbol) or self._rhs.requires(symbol)
		elif self._op == "||":
			return self._lhs.requires(symbol) and self._rhs.requires(symbol)
		else:
			return False

	def format(self, kconfig = None):
		if self._lhs is None:
			return "%s(%s)" % (self._op, self._rhs.format(kconfig))
		else:
			return "(%s %s %s)" % (self._lhs.format(kconfig), self._op, self._rhs.format(kconfig))

	def __repr__(self):
		if self._lhs is None:
			return "%s(%s)" % (self._op, self._rhs)
		else:
			return "(%s %s %s)" % (self._lhs, self._op, self._rhs)

