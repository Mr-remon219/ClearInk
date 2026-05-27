class skill:
    def __init__(self):
    ## value每个skill的name，discrption，content，key为name
    AVAILABLE_SKILLS: dict[str, dict] = {}
    self._scan_skill()

    ## 可以扫描SKILLS_DIR文件夹下的文件夹，将文件夹内的skill.md的前三行name,discrption,content存放给AVAILABLE_SKILLS
    def _scan_skill(self)->None

    ## 将AVAILABLE_SKILLS内的所有value的name,discrption两项取出拼成str返回
    def list_skill(self)->str