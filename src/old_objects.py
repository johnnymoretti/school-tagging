from time import localtime, strftime
from google.appengine.ext import ndb
from google.appengine.api import memcache
import logging

def nowtime():
	return strftime("%Y-%m-%d-%H:%M:%S", localtime())

class Person(ndb.Model):
	name = ndb.StringProperty()
	currentLesson = ndb.StringProperty()
	#~ connected = ndb.BooleanProperty()
	token = ndb.StringProperty()

class Teacher(Person):
	lessons = ndb.StringProperty(repeated=True)
	def safe_put(self):
		memcache.set("teacher:" + self.name, self)
		self.put()
		
class Student(Person):
	answers = ndb.PickleProperty()
	
	def safe_put(self):
		memcache.set("student:" + self.name, self)
		self.put()

class Lesson(ndb.Model):
	name = ndb.StringProperty()
	sessions = ndb.StringProperty(repeated=True)
	teacher = ndb.StringProperty()
	students = ndb.StringProperty(repeated=True)
	currentSession = ndb.StringProperty()
	status = ndb.StringProperty()
	
	def safe_put(self):
		memcache.set("lesson:" + self.name, self)
		self.put()

def addTeacher(strTeacher, strToken, strLesson):
	objTeacher = Teacher(id=strTeacher)
	objTeacher.name = strTeacher
	objTeacher.lessons = []
	objTeacher.token = strToken
	objTeacher.currentLesson = strLesson
	#~ objTeacher.connected = True
	objTeacher.safe_put()
	updateTeachersList("add", strTeacher)
	return objTeacher


def getTeachersList():
	lst = memcache.get("teachers_list")
	if not lst:
		lst = []
		q = Teacher.query()
		if q.get():
			lst = [t.name for t in q]
		memcache.add("teachers_list", lst)
	return lst
				
def updateTeachersList(command, strTeacher):
	lst = getTeachersList()
	if command == "add":
		lst.append(strTeacher)
	elif command == "remove":
		lst.remove(strTeacher)
	memcache.set("teachers_list", lst)
	return

def updateLessonList(command, strLesson):
	lst = getLessonList()
	if command == "add":
		lst.append(strLesson)
	elif command == "remove":
		lst.remove(strLesson)
	memcache.set("lesson_list", lst)
	return
	
def addStudent(strStudent, strToken, strLesson):
	objStudent = Student(id=strStudent)
	objStudent.name = strStudent
	objStudent.token = strToken
	objStudent.currentLesson = strLesson
	objStudent.answers = {}
	#~ objStudent.connected = True
	objStudent.safe_put()
	return objStudent

def disconnect_student(strStudent):
	student = getStudent(strStudent)
	if student:
		#~ student.connected = False
		student.token = ""
		student.safe_put()

def disconnectTeacher(strTeacher):
	objTeacher = getTeacher(strTeacher)
	if objTeacher:
		objTeacher.token = ""
		objLesson = getLesson(objTeacher.currentLesson)
		objLesson.status = "ended"
		objLesson.safe_put()
		
		objTeacher.currentLesson = ""
		objTeacher.safe_put()
		
		
#~ def connect_student(strStudent):
	#~ student = getStudent(strStudent)
	#~ if student and not student.connected:
		#~ student.connected = True
		#~ student.safe_put()
	
def getStudentList(strTeacher):
	"""return list of string students for the current lesson of the teacher."""
	objTeacher = getTeacher(strTeacher)
	if objTeacher:
		strCurrentLesson = objTeacher.currentLesson
		objCurrentLesson = getLesson(strCurrentLesson)
		students = [s for s in objCurrentLesson.students \
							if getStudent(s).token != ""]
		return students
	else:
		return False
	
def getTeacher(strTeacher):
	t = memcache.get("teacher:" + strTeacher)
	if not t:
		k = ndb.Key("Teacher", strTeacher)
		t = k.get()
		memcache.add("teacher:" + strTeacher, t)
	return t

def getStudent(strStudent):
	t = memcache.get("student:" + strStudent)
	if not t:
		k = ndb.Key("Student", strStudent)
		if k.get():
			t = k.get()
			memcache.add("student:" + strStudent, t)
	return t

def addLesson(strTeacher, strToken, strLesson):
	objTeacher = addTeacher(strTeacher, strToken, strLesson)
	objLesson = Lesson(id=strLesson)
	objLesson.name = strLesson
	objLesson.teacher = strTeacher
	objLesson.status = "running"
	objLesson.safe_put()
	updateLessonList("add", strLesson)
	return objLesson

def getLesson(strLesson):
	t = memcache.get("lesson:" + strLesson)
	if not t:
		k = ndb.Key("Lesson", strLesson)
		t = k.get()
		memcache.add("lesson:" + strLesson, t)
	return t

def getLessonList():
	lst = memcache.get("lesson_list")
	if not lst:
		lst = []
		q = Lesson.query()
		if q.get():
			lst = [t.name for t in q]
		memcache.add("lesson_list", lst)
	return lst

def getRunningLessonList():
	lst = getLessonList()
	return [lesson for lesson in lst if getLesson(lesson).status == "running"]
		

def joinLesson(strStudent, strToken, strLesson):
	#~ objTeacher = getTeacher(strTeacher)
	#~ strLesson = objTeacher.currentLesson
	objStudent = addStudent(strStudent, strToken, strLesson)
	objLesson = getLesson(strLesson)
	if strStudent not in objLesson.students:
		objLesson.students.append(strStudent)
	objLesson.safe_put()
	return True

def checkInLesson(strStudent, strLesson):
	objStudent = getStudent(strStudent)
	if objStudent and objStudent.currentLesson == strLesson:
		objLesson = getLesson(strLesson)
		if strStudent not in objLesson.students:
			objLesson.students.append(strStudent)
			objLesson.safe_put()
		return True
	else:
		return False
	
	
class Session(ndb.Model):
	start = ndb.StringProperty()
	exercise = ndb.PickleProperty()
	exerciseType = ndb.PickleProperty()
	lesson = ndb.StringProperty()
	students = ndb.StringProperty(repeated=True)
	
	def safe_put(self):
		memcache.set("session:" + self.start, self)
		self.put()
	def is_correct(self, answer):
		if self.exerciseType["type"] == "find_element":
			answer = int(answer)
			answers = self.exerciseType["answers"]
		elif self.exerciseType["type"] == "which_type":
			answers = [self.exerciseType["options"][a] for a in self.exerciseType["answers"]]
		return answer in answers

def add_session(objLesson, objExercise, objExerciseType):
	strSession = nowtime()
	objSession = Session(id=strSession)
	objSession.start = strSession
	objSession.lesson = objLesson.name
	objSession.exercise = objExercise
	objSession.exerciseType = objExerciseType
	objSession.students = objLesson.students
	objSession.safe_put()
	objLesson.currentSession = strSession
	if strSession not in objLesson.sessions:
		objLesson.sessions.append(strSession)
	objLesson.safe_put()
	return strSession

def get_session(strSession):
	t = memcache.get("session:" + strSession)
	if not t:
		k = ndb.Key("Session", strSession)
		t = k.get()
		memcache.add("session:" + strSession, t)
	return t

def add_answer(objStudent, objLesson, strAnswer):
	strSession = objLesson.currentSession
	objSession = get_session(strSession)
	if strSession in objStudent.answers.keys():
		objStudent.answers[strSession].append(strAnswer)
	else:
		objStudent.answers[strSession] = [strAnswer]
	booCorrect = objSession.is_correct(strAnswer)
