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

_COLORS = {
	"red":		31,
	"green":	32,
	"yellow":	33,
	"blue":		34,
	"violet":	35,
	"cyan":		36,
	"gray":		37,
}

def colorize_text(text, color):
	colorcode = _COLORS[color]
	return "\x1b[%dm%s\x1b[0m" % (colorcode, text)

def expand_tabs(text, tabsize = 8):
	result = ""
	for char in text:
		if char == "\t":
			new_length = (len(result) + tabsize) // tabsize * tabsize
			tab_length = new_length - len(result)
			result += " " * tab_length
		else:
			result += char
	return result

def apparent_length(text, tabsize = 8):
	length = 0
	for char in text:
		if char == "\t":
			length = (length + tabsize) // tabsize * tabsize
		else:
			length += 1
	return length

if __name__ == "__main__":
	assert(apparent_length("\t  ", tabsize = 4) == 6)
	assert(apparent_length("\t  ", tabsize = 8) == 10)
	assert(apparent_length(" \t", tabsize = 8) == 8)
