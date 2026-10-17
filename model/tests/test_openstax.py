import xml.etree.ElementTree as ET

from parser_model.openstax import extract_module, flatten

XML = """<document xmlns="http://cnx.rice.edu/cnxml" xmlns:m="http://www.w3.org/1998/Math/MathML">
<title>Free Fall</title>
<content>
<exercise id="e1"><problem id="p1"><para>A rocket accelerates at 20 m/s<sup>2</sup> for
<m:math><m:mrow><m:mn>5</m:mn><m:mtext>s</m:mtext></m:mrow></m:math>.
Find v<sub>f</sub>.</para></problem>
<solution id="s1"><para>v = <m:math><m:mfrac>
<m:mn>1</m:mn><m:mn>2</m:mn></m:mfrac></m:math></para></solution>
</exercise>
<exercise id="e2"><problem id="p2"><para>No solution here.</para></problem></exercise>
</content></document>"""


def test_flatten_handles_sup_sub_and_mathml():
    root = ET.fromstring(XML)
    problem = next(root.iter("{http://cnx.rice.edu/cnxml}problem"))
    assert flatten(problem) == "A rocket accelerates at 20 m/s^2 for 5s. Find v_f."


def test_extract_module(tmp_path):
    module = tmp_path / "m58286"
    module.mkdir()
    (module / "index.cnxml").write_text(XML)
    records = extract_module(module / "index.cnxml", "ch3-straight-line")
    assert [r["id"] for r in records] == ["openstax-v1/m58286/e1", "openstax-v1/m58286/e2"]
    assert records[0]["solution"] == "v = (1)/(2)"
    assert records[1]["solution"] is None
    assert records[0]["license"] == "CC BY 4.0" and records[0]["section"] == "Free Fall"
