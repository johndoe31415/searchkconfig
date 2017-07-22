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

import tpg
from KConfigObjects import Symbol, Source, ConfigurationItem, Menu, ConfigType, Option, Comparison, DefaultValue, DependsOn, Select, DefType, Conditional, Range, Comment, Imply, VisibleIf, Literal

def _to_int(value):
	if value.startswith("0x"):
		return int(value, 16)
	else:
		return int(value)

class KConfigParser(tpg.VerboseParser):
	r"""
		set lexer = ContextSensitiveLexer
		separator space			'\s+';

		token kw_config			'config|menuconfig';
		token kw_menu			'menu|mainmenu';
		token kw_option			'option';
		token kw_source			'source';
		token kw_if				'if';
		token kw_endif			'endif';

		token intval			'0x[0-9a-fA-F]+|-?\d+'		$ _to_int

		token kw_type			'(string|hex|bool|prompt|tristate|int)';
		token kw_deftype		'(def_bool|def_tristate)';
		token kw_range			'range';
		token kw_default		'default';
		token kw_select			'select';
		token kw_imply			'imply';
		token kw_depends_on		'depends on';
		token kw_visible_if		'visible if';
		token kw_help			"---help---|help";

		token kw_choice			"choice";
		token kw_endchoice		"endchoice";

		token cmp_op			'=|!=|&&|\|\||>=|<=|>|<';
		token unary_op			'!';
		token comment			'#[^\n]*';
		token symbol			'[A-Za-z0-9_]+'		$ Symbol

		START/s -> ConfigurationItem/s;

		QuotedString/s ->
			'"' '(\\"|[^"])*'/s '"'					$ s = Literal(s.replace("\\\"", "\""))
			| '\'' '[^\']*'/s '\''					$ s = Literal(s.replace("\\'", "'"))
		;

		String/s ->
			QuotedString/s
			| '[^\s]+'/s							$ s = Literal(s)
		;

		ConfigurationItem/c ->
			(																						$ expr = None
				kw_config/key symbol/s																$ c = ConfigurationItem(conftype = key, symbol = s)
				| kw_menu/key String/s																$ c = Menu(menutype = key, text = s)
				| 'source'/key String/s																$ c = Source(filename = s)
				| 'comment'/key String/s															$ c = Comment(text = s)
				| kw_type/t String/s (kw_if Expression/expr)?										$ c = ConfigType(typename = t, text = s, condition = expr)
				| kw_type/t																			$ c = ConfigType(typename = t, text = None, condition = None)
				| kw_deftype/t Expression/s (kw_if Expression/expr)?								$ c = DefType(typename = t, value = s, condition = expr)
				| kw_range (intval/r0|symbol/r0) (intval/r1|symbol/r1) (kw_if Expression/expr)?		$ c = Range(fromvalue = r0, tovalue = r1, condition = expr)
				| kw_depends_on Expression/expr														$ c = DependsOn(expr)
				| kw_option '[^\n]*'/s																$ c = Option(parameters = s)
				| kw_default Expression/e (kw_if Expression/expr)?									$ c = DefaultValue(value = e, condition = expr)
				| kw_select symbol/s (kw_if Expression/expr)?										$ c = Select(symbol = s, condition = expr)
				| kw_imply symbol/s (kw_if Expression/expr)?										$ c = Imply(symbol = s, condition = expr)
				| kw_visible_if Expression/expr														$ c = VisibleIf(condition = expr)
				| kw_if Expression/expr																$ c = Conditional(condition = expr)
			)
			comment?
		;

		ConditionalSymbol/<symbol, condition> ->
																						$ condition = None
			symbol/symbol (kw_if Expression/condition)?
		;

		Expression/e ->
			(
				unary_op/op Expression/e												$ e = Comparison(lhs = None, op = op, rhs = e)
				| Term/lhs cmp_op/op Expression/rhs										$ e = Comparison(lhs = lhs, op = op, rhs = rhs)
				| Term/e
			)
		;

		Term/t ->
			(
				'\(' Expression/t '\)'
				| '[ynm]'/t																$ t = Literal(t)
				| symbol/t
				| String/t
			)
		;

		"""
	verbose = 0

if __name__ == "__main__":
	KConfigParser.verbose = 2

	def show_error(text, line, column):
		ctx = 2
		text = text.split("\n")
		for lineno in range(line - ctx - 1, line + ctx):
			if (lineno < 0) or (lineno >= len(text)):
				continue
			print("%4d: %s" % (lineno + 1, text[lineno]))
			if (lineno + 1 == line):
				print("      " + (" " * (column - 1)) + "^")

	def try_parse(text, filename = None):
		print("-" * 120)
		parser = KConfigParser()
		try:
			parsed = parser(text)
		except tpg.SyntacticError as e:
			print(e)
			if filename is not None:
				print(filename)
			show_error(text, e.line, e.column)
			parsed = None
		return parsed

	print(try_parse("def_bool ALPHA || M68K || SPARC || X86_32 || IA32_EMULATION"))
	print(try_parse("def_bool y if X86_64"))
	print(try_parse("default \"elf32-i386\" if X86_32"))
	print(try_parse("default ARCH != \"i386\""))
	print(try_parse("default ARCH_MXC || SOC_IMX28 if ARM"))
	print(try_parse("default !IA64 && !(TILE && 64BIT)"))

