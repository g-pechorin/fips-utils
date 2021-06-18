'''
compress.py

compress and embed trees of files into your workspace
'''

Version = 2

import sys
import os.path
import yaml
import genutil
import zlib
import re


#-------------------------------------------------------------------------------
def generate(input, out_src, out_hdr) :
	if genutil.isDirty(Version, [input], [out_hdr]) :
		with open(input, 'r') as f :
			conf = yaml.load(f)
		
		# strip the zlib checksums
		strip = True
		if 'strip' in conf:
			strip = strip and conf['strip']
		
		# (cosmetic) how many bytes per line
		line = 32
		if 'line' in conf:
			line = conf['line']
		
		# compression level
		level = zlib.Z_BEST_COMPRESSION
		if 'level' in conf:
			level = eval(conf['level'])
		
		# allow rewriting of the files
		replace = lambda name, src: src
		if 'replace' in conf:
			replace = eval(conf['replace'])
		def rewrite(name, src):
			out = replace(name, src)
			if out == src:
				return src
			else:
				return rewrite(name, out)
		
		# where to scan for files, what to include, then what to remove from that
		root = conf['root']

		# by default; include all none .orig files
		take = '.*(?<!\\.orig)$'
		if 'take' in conf:
			take = conf['take']
		if not isinstance(take, list):
			take = [take]
		def want(name):
			for pat in take:
				if re.match(pat, name):
					print('### ' + root + ' -> ' + name)
					return True
			return False
		
		echo = False
		if 'echo' in conf:
			echo = echo or conf['echo']


		# build the/a full list of files to include
		def sub(path):
			out = []
			for file in os.listdir(path):
				if os.path.isfile(os.path.join(path, file)):
					out.append(file)
				else:
					for baby in sub(os.path.join(path, file)):
						out.append(file + '/' + baby)
			return out
		full = []
		for seen in sub(root):
			if want(seen):
				full.append(seen)

		with open(out_hdr, 'w') as f:
			f.write('// #version:{}#\n'.format(Version))
			f.write('// machine generated, do not edit!\n')
			
			idx = -1
			items = []
			for name in full:
				with open(os.path.join(root, name), 'rb') as file:
					src = file.read()
					raw = rewrite(name, src)
					f.write('// {}: {}\n'.format(idx+1, name))
					if echo:
						f.write('\t\t#if 0\n')
						f.write('\t\t\traw={}\n'.format(len(src)))
						for txt in src.decode('utf-8').replace('\r\n', '\n').split('\n'):
							f.write('\t\t\t\t'+txt+'\n')
						f.write('\t\t\tsrc={}\n'.format(len(raw)))
						for txt in raw.decode('utf-8').split('\n'):
							f.write('\t\t\t\t'+txt+'\n')
						f.write('\t\t#endif\n')
					if 0 == len(raw):
						items.append('\t{{ "{}", true, nullptr, 0, nullptr, 0 }},\n'.format(name))
					else:
						idx += 1
						zip = zlib.compress(raw, level)
						if strip:
							# strip the two lead bytes so we don't need TINFL_FLAG_PARSE_ZLIB_HEADER
							zip = zip[2:]

						f.write('static uint8_t raw{}[{}];\n'.format(idx, len(raw)))
						f.write('static const uint8_t zip{}[] = {{\n\t'.format(idx))

						num = 0
						dop = False
						for byte in zip:
							if dop:
								f.write('\n\t')
							if sys.version_info[0] >= 3:
								f.write(hex(ord(chr(byte))) + ', ')
							else:
								f.write(hex(ord(byte)) + ', ')
							num += 1
							dop = (0 == num % line)

						f.write('\n};\n')

						items.append('\t{{ "{}", false, zip{}, sizeof(zip{}), raw{}, sizeof(raw{}) }},\n'.format(name, idx, idx, idx, idx))
			
			f.write('struct item_t { const char* _name; bool _hot; const uint8_t* _zip_data; const size_t _zip_size; uint8_t* _raw_data; size_t _raw_size; };\n')
			f.write('item_t item_p[] = {\n');
			for item in items:
				f.write(item)

			f.write('\n\t{nullptr}\n');
			f.write('};\n');
