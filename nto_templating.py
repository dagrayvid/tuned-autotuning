from jinja2 import Environment, FileSystemLoader

def template_from_tunable_dict(tunables, template_file, output_file):
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template(template_file)
    output_from_parsed_template = template.render(tunables=tunables)
    #print("Parsed tuned.conf.j2 template:")
    #print(output_from_parsed_template)

    with open(output_file, "w+") as f:
        f.write(output_from_parsed_template)
