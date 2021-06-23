'''
compress.py

compress and embed trees of files into your source code



// looks like this;


const void* src(const char* name, size_t& len)noexcept
{
	// it'd be swell if we could decompress without caching for stuff that'll only be used once
	// ... which is everything in this project


#define compressed_begin()	\
	static struct { \
		const char* _name; \
		const size_t _zip_size; \
		const void* _zip_data; \
		void* _raw_data; \
		const size_t _raw_size; \
	} compressed_archive[] = {

#define compressed(SRC_NAME, INDEX, ZIP_SIZE, ZIP_DATA, RAW_ITEM, RAW_SIZE)	{SRC_NAME, ZIP_SIZE, ZIP_DATA, nullptr, RAW_SIZE},
#define compressed_close() {nullptr} };

#include "../src.inc"

	// ... so, for now; if "filename == null" we free whatever has been allocated
	if (!name)
	{
		len = 0;
		for (auto item = compressed_archive; item->_name; item++)
			if (item->_raw_data)
			{
				free(item->_raw_data);
				item->_raw_data = nullptr;
				len += item->_raw_size;
			}
		return nullptr;
	}

	// search for a record to read
	for (auto item = compressed_archive; item->_name; item++)
	{
		// is this not the record we're looking for?
		if (!se(name, item->_name))
			continue;

		if (!item->_raw_data)
			tinfl(
				item->_raw_data = malloc(item->_raw_size),
				item->_raw_size,
				item->_zip_data, item->_zip_size
			);

		// do the output
		len = item->_raw_size;
		return item->_raw_data;
	}

	return nullptr;
}






'''

Version = 3

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
		line = 18
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
		# .. need to offset from the config file
		root = input[:input.rindex('/')] +'/' + conf['root']

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

					# write the "header"
					f.write('// {}: {}\n'.format(idx+1, name))

					# write the contents ... which can be bigbig and crashy so don't
					if echo:
						f.write('\t\t#if 0\n')
						f.write('\t\t\traw={}\n'.format(len(src)))
						for txt in src.decode('utf-8').replace('\r\n', '\n').split('\n'):
							f.write('\t\t\t\t'+txt+'\n')
						f.write('\t\t\tsrc={}\n'.format(len(raw)))
						for txt in raw.decode('utf-8').split('\n'):
							f.write('\t\t\t\t'+txt+'\n')
						f.write('\t\t#endif\n')
					
					# increment the counter
					idx += 1

					# need one thing for "blank" and something else for full
					if 0 == len(raw):
						f.write('#define zip{} ((uint8_t*)nullptr)\n'.format(idx))
						items.append('\tcompressed("{}", {}, 0, zip{}, raw{}, 0)\n'.format(name, idx, idx, idx))
					else:
						# compress the file
						zip = zlib.compress(raw, level)
						if strip:
							# strip the two lead bytes so we don't need TINFL_FLAG_PARSE_ZLIB_HEADER
							zip = zip[2:]
						
						# begin!
						f.write('static const uint8_t zip{}[{}] = {{\n\t'.format(idx, len(zip)))

						num = 0
						dop = False
						for byte in zip:
							if dop:
								f.write('\n\t')
							sttr = '0x' + (''.join('%02x' % byte).upper())
							f.write(sttr + ', ' )
							num += 1
							dop = (0 == num % line)

						# finish the compressed block
						f.write('\n};\n')

						# write the "item"
						items.append('\tcompressed("{}", {}, {}, zip{}, raw{}, {})\n'.format(name, idx, len(zip), idx, idx, len(raw)))
			
			f.write('compressed_begin()\n');
			for item in items:
				f.write(item)

			f.write('compressed_close()\n');
