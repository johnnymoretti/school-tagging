# coding: utf-8
# [school-tagging] webapp

import lessonLogic as logic
import webapp2
import jinja2
import os
import re
import random
import string
import hashlib
import logging
import json
from google.appengine.api import channel
from google.appengine.ext import ndb
from google.appengine.api import memcache

def getExerciseList():
	lst = memcache.get("exercise_list")
	if not lst:
		lst = json.loads(open("lists/exercises.json").read())
		memcache.set("exercise_list", lst)
	return lst
	
class AppUser(ndb.Model):
	username = ndb.StringProperty()
	role = ndb.StringProperty()
	token = ndb.StringProperty()
	hashpassword = ndb.StringProperty()
	status = ndb.StringProperty()
	currentLesson = ndb.StringProperty()

class User():
	RE_USERNAME = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
	RE_PASSWORD = r"^.{3,20}$"
	
	def __init__(self):
		self.username = ""
		self.password = ""
		self.hashpassword = ""
		self.role = ""
		self.token = ""
		self.salt = ""
		self.status = ""
		self.currentLesson = ""
	
	def save(self):
		#~ appuser = AppUser(id=self.username)
		#~ appuser = AppUser()
		q = AppUser.query(AppUser.username == self.username,
							AppUser.currentLesson == self.currentLesson)
		appuser = q.get()
		if not appuser:
			appuser = AppUser()
		appuser.username = self.username
		appuser.role = self.role
		appuser.hashpassword = self.hashpassword
		appuser.token = self.token
		appuser.status = self.status
		appuser.currentLesson = self.currentLesson
		key = appuser.put()
		#~ memcache.set("%s:appuser" % self.username, self)
		memcache.set("%s:appuser|%s:currentLesson" % \
						(self.username, self.currentLesson), self)
		return key
		
	def get(self):
		"""overwrite self with appuser from ndb. return true if OK"""
		appuser = memcache.get("%s:appuser|%s:currentLesson" % \
						(self.username, self.currentLesson))
		if appuser is None:
			q = AppUser.query(AppUser.username == self.username)
			if q.get():
				appuser = q.get()
				memcache.add("%s:appuser|%s:currentLesson" % \
						(self.username, self.currentLesson), appuser)
			else:
				MyLogs("User.get: Username not found in ndb")
				return None
		if appuser.role == "teacher":
			if self.hashpassword == "":
				self.salt = appuser.hashpassword.split("|")[1]
				self.makeHashpassword()
			if self.hashpassword == appuser.hashpassword:
				#~ self.role = appuser.role
				self.token = appuser.token
				self.status = appuser.status
				#~ self.currentLesson = appuser.currentLesson
				return True
			else:
				MyLogs("User.get: password in db doesn't match")
				return False
		else:
			#~ self.role = appuser.role
			self.token = appuser.token
			self.status = appuser.status
			#~ self.currentLesson = appuser.currentLesson
			return True
	
	def simple_get(self):
		"""used only for channel connection or disconnection"""
		appuser = memcache.get("%s:appuser|%s:currentLesson" % \
						(self.username, self.currentLesson))
		if appuser is None:
			q = AppUser.query(AppUser.username == self.username)
			if q.get():
				appuser = q.get()
				memcache.add("%s:appuser|%s:currentLesson" % \
						(self.username, self.currentLesson), appuser)
			else:
				MyLogs("User.simple_get: Username not found in ndb")
				return None
			self.role = appuser.role
			self.token = appuser.token
			self.status = appuser.status
			self.currentLesson = appuser.currentLesson
			return True
			
	def setUsername(self, username):
		self.username = username
		return
	
	def setCurrentLesson(self, currentLesson):
		self.currentLesson = currentLesson
		return
		
	def setPassword(self, password):
		self.password = password
		return
		
	def setHashpassword(self, hashpassword):
		self.hashpassword = hashpassword
		return
	
	def setVerifyPassword(self, verify):
		self.verifyPassword = verify
		return
	
	def setRole(self, role):
		self.role = role
		return
	
	def setStatus(self, status):
		self.status = status
		return
		
	def makeSalt(self):
		return ''.join(random.choice(string.letters) for x in xrange(5))
	
	def makeHashpassword(self):
		if self.salt == "":
			self.salt = self.makeSalt()
		cript = self.username + self.password + self.salt
		encr_password = hashlib.sha256(cript).hexdigest()
		self.hashpassword = "%s|%s" % (encr_password, self.salt)

	def twoPasswordsMatch(self):
		""" return True if the two inserted psw match. """
		match = self.password == self.verifyPassword
		if match:
			return True
		else:
			MyLogs("The two passwords don't match")

	def passwordMatchesRE(self):
		""" return True if the psw matches the regular expression. """
		re_password = re.compile(self.RE_PASSWORD)
		if re_password.match(self.password):
			return True
		else:
			MyLogs("Password doesn't match the regex")
			return False
	
	def passwordIsValid(self):
		""" return True if the password matches the two rules above.
		also setup the hashpassword.
		
		"""
		result = self.passwordMatchesRE() and self.twoPasswordsMatch()
		if result:
			self.makeHashpassword()
			return True
		else:
			MyLogs("Password rejected. See log above")
			return False

	def usernameIsValid(self):
		""" return True if the inserted username matchs the re. """
		re_username = re.compile(self.RE_USERNAME)
		if re_username.match(self.username):
			return True
		else:
			MyLogs("Username rejected (it doesn't match the regex)")
			return False
	
	def setChannel(self):
		if self.token == "":
			token = channel.create_channel(self.username)
			if token:
				self.token = token
				self.status = "connected"
				self.save()
			else:
				MyLogs("Channel creation failure")
				return False
		return True

	def logout(self):
		self.token = ""
		self.status = "disconnected"
		self.currentLesson = ""
		if self.role == "student":
			logic.disconnect_student(self.username)
		else:
			logic.disconnectTeacher(self.username)
		self.save()

	def usernameNotYetExisting(self):
		if self.get() == None:
			return True
		else:
			return False

	def studentNameNotInUse(self, lesson):
		if self.get() == None or self.currentLesson != lesson:
			MyLogs("Student name not in use")
			return True
		else:
			MyLogs("Student name already used")
			return False
		
		
	#~ def updateAttr(self, attribute):
		#~ appuser = self.getAppUser()
		#~ if appuser:
			#~ setattr(appuser, attribute, getattr(self, attribute))
			#~ if appuser.safePut():
				#~ return True
			#~ else:
				#~ MyLogs("updateAttr", attribute, ":safe put didn't work")
		#~ else:
			#~ MyLogs("updateAttr", attribute, ":error. user not retrieved")
		#~ return False
	
	#~ def validUser(self):
		""" check if the user is entitled to login.
		input=username string and password not hashed
		return True if user is valid.
		
		"""
		#~ user = self.getAppUser()
		#~ if user:
			#~ if self.hashpassword == "":
				#~ self.salt = user.hashpassword.split("|")[1]
				#~ self.makeHashpassword()
			#~ if self.hashpassword == user.hashpassword:
				#~ self.role = user.role
				#~ self.token = user.token
				#~ self.loginStatus = "logged"
				#~ self.updateAttr("loginStatus")
				#~ return True
			#~ else:
				#~ MyLogs("Password incorrect for user", self.username)
		#~ else:
			#~ MyLogs("Username not in database")
			#~ return False

class UserCookie():

	def __init__(self, value=""):
		self.username = ""
		self.hashpassword = ""
		self.role = ""
		self.password = ""
		self.salt = ""
		self.value = value
		if value:
			self.extractValue()

	def setValue(self, role, username, hashpassword):
		self.role = str(role)
		self.username = str(username)
		self.hashpassword = str(hashpassword)
	
	def stringify(self):
		self.value = "|".join([self.role, self.username, self.hashpassword])

	def send(self, http_self):
		self.stringify()
		http_self.response.set_cookie('schooltagging-user', self.value)
			
	def extractValue(self):
		self.role = self.value.split("|")[0]
		self.username = self.value.split("|")[1]
		if len(self.value.split("|")) > 3:
			self.password = self.value.split("|")[2]
			self.salt = self.value.split("|")[3]
			self.hashpassword = self.password + "|" + self.salt

class LessonCookie():

	def __init__(self, lesson=""):
		self.lesson = lesson

	def setValue(self, lesson):
		self.lesson = str(lesson)

	def send(self, http_self):
		http_self.response.set_cookie('schooltagging-lesson', self.lesson)
			
class MyLogs():
	def __init__(self, *a):
		message = " ".join([str(chunk) for chunk in a])
		logging.info(str(message))

class MainHandler(webapp2.RequestHandler):
	template_dir = os.path.join(os.path.dirname(__file__), 'pages')
	jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
		autoescape = True)
	def writeout(self, *a, **kw):
		self.response.out.write(*a, **kw)
	
	def readout(self,param):
		return self.request.get(param)
		
	def render_str(self, template, **params):
		return self.jinja_env.get_template(template).render(params)
		
	def render_page(self, template, **kw):
		self.writeout(self.render_str(template, **kw))
	
	def getUserCookie(self):
		return self.request.cookies.get("schooltagging-user")
	
	def getLessonCookie(self):
		return self.request.cookies.get("schooltagging-lesson")
		
	def validUserFromCookie(self):
		""" check if the request is coming from a valid user.
		return the user object if valid, else False
		
		"""
		usercookie = UserCookie(self.getUserCookie())
		lessoncookie = LessonCookie(self.getLessonCookie())
		if usercookie.value and lessoncookie.lesson:
			user = User()
			user.setUsername(usercookie.username)
			user.setHashpassword(usercookie.hashpassword)
			user.setCurrentLesson(lessoncookie.lesson)
			if user.get():
				return user
			else:
				MyLogs("MainHandler:Invalid cookie")
		else:
			MyLogs("MainHandler:cookie is not existing or has not value")
		return False
		
	def clearCookies(self):
		""" clear my cookie if existing.
		input=server response
		return True if cookie existed and has been eliminated,
		return False if cookie wasn't existing
		
		"""
		self.response.delete_cookie('schooltagging-lesson', path = '/')
		cookie = UserCookie(self.request.cookies.get("schooltagging-user"))
		if cookie.value:
			self.response.delete_cookie('schooltagging-user', path = '/')
			return True
		else:
			return False

class ConnectionHandler(MainHandler):
	def post(self, action):
		username = self.request.get('from')
		user = User()
		user.setUsername(username)
		if user.simple_get():
			if action == "disconnected":
				user.status = "disconnected"
				if user.role != "student":
					logic.disconnectTeacher(user.username)
			elif action == "connected":
				user.status = "connected"
			
			user.save()
		return
		#~ user = logic.getStudent(username)
		#~ if action == "disconnected" and user:
			#~ logic.disconnect_student(username)

class TeacherHandler(MainHandler):
	error = ""
		
	def get(self, action):
		if action == "signup":
			return self.render_page("signup.html", error=self.error)
		elif action == "login":
			return self.render_page("login.html", error=self.error)
		elif action == "logout":
			self.logout()
			return self.render_page("login.html", error=self.error)
		elif action == "dashboard":
			user = self.validUserFromCookie()
			if user:
				exerciseList = getExerciseList()
				studentsList = logic.getStudentList(user.username) or []
				self.render_page("teacher_dashboard.html",
							username = user.username,
							token = user.token,
							exercise_list = exerciseList,
							students_list = studentsList,
							)
			else:
				return self.redirect("/t/login")
		elif action == "exercise_list_request":
			user = self.validUserFromCookie()
			if user:
				message = {
					"type": "exercises_list",
					"message": getExerciseList(),
					}
				message = json.dumps(message)
				channel.send_message(user.token, message)
			else:
				return self.redirect("/t/login")
		else:  # fallback
			return self.redirect("/t/login")
	
	def post(self, action):
		if action == "signup":
			return self.signup()
		elif action == "login":
			return self.login()
		user = self.validUserFromCookie()
		if user:
			if action == "exercise_request":
					type = self.request.get("type")
					id = self.request.get("id")
					exerciseList = getExerciseList()
					objLesson = logic.getLesson(self.getLessonCookie())
					objExercise = [e for e in exerciseList if e["id"] == id][0]
					objType = [t for t in objExercise["goals"] if t["type"] == type][0]
					strIdSession = logic.add_session(objLesson, objExercise, objType)
					objSession = logic.get_session(strIdSession)
					self.sendExerciseToStudents(
								objExercise,
								objSession.students,
								objType,
								)
	
	def login(self):
		self.clearCookies()
		user = User()
		user.setUsername(self.request.get("username"))
		user.setPassword(self.request.get("password"))
		if user.usernameIsValid():
			if user.get():
				user.setChannel()
				cookie = UserCookie()
				cookie.setValue(
							user.role,
							user.username,
							user.hashpassword,
							)
				cookie.send(self)
				strLessonName = self.request.get("lessonName")
				lessoncookie = LessonCookie()
				lessoncookie.setValue(strLessonName)
				lessoncookie.send(self)
				logic.addLesson(user.username, user.token, strLessonName)
				return self.redirect("/t/dashboard")

			else:
				self.error = "Invalid login"
		else:
			self.error = "Username not valid"
		return self.render_page("login.html", error=self.error)

	def signup(self):
		self.clearCookies()
		user = User()
		user.setUsername(self.request.get("username"))
		user.setPassword(self.request.get("password"))
		user.setVerifyPassword(self.request.get("verify"))
		strLessonName = self.request.get("lessonName")
		user.setCurrentLesson(strLessonName)
		user.setRole("teacher")
		if user.usernameNotYetExisting():
			if user.usernameIsValid():
				if user.passwordIsValid():
					user.save()
					user.setChannel()
					cookie = UserCookie()
					cookie.setValue(
								user.role,
								user.username,
								user.hashpassword,
								)
					cookie.send(self)
					lessoncookie = LessonCookie()
					lessoncookie.setValue(strLessonName)
					lessoncookie.send(self)
					logic.addLesson(user.username, user.token, strLessonName)
					
					return self.redirect("/t/dashboard")

				else:
					self.error = "Password not valid"
			else:
				self.error = "Username not valid"
		else:
			self.error = "Username already existing"
		return self.render_page("signup.html", error=self.error)

	def logout(self):
		cookie = UserCookie(self.getUserCookie())
		if cookie.value:
			user = User()
			user.username = cookie.username
			user.hashpassword = cookie.hashpassword
			if user.get():
				user.logout()
				self.clearCookies()
			else:
				MyLogs("Invalid cookie")
		else:
			MyLogs("cookie is not existing or has not value")
		self.redirect("/t/login")
	
	def sendExerciseToStudents(self, exercise, students, type):
		message = {
			"type": "exercise",
			"message": {
				"exercise": exercise,
				"type": type,
				},
			}
		message = json.dumps(message)
		for student in students:
			user = logic.getStudent(student)
			channel.send_message(user.token, message)
			
class StudentHandler(MainHandler):
	error = ""		
	
	def get(self, action):
		if action == "login":
			return self.render_page("student_login.html", error=self.error)
		elif action == "dashboard":
			user = self.validUserFromCookie()
			if user:
				assert user.role == "student"
				strLessonName = self.getLessonCookie()
				if not logic.checkInLesson(user.username, strLessonName):
					self.response.delete_cookie('schooltagging-lesson', path = '/')
				#~ logic.connect_student(user.username)
				return self.render_page("student_dashboard.html",
							username = user.username,
							token = user.token,
							)
			else:
				return self.redirect("/s/login")
		else:  # fallback
			return self.redirect("/s/login")
	
	def post(self, action):
		if action == "login":
			return self.login()
		elif action == "answer":
			user = self.validUserFromCookie()
			if user:
				objStudent = logic.getStudent(user.username)
				objLesson = logic.getLesson(self.getLessonCookie())
				strTeacher = objLesson.teacher
				objTeacher = logic.getTeacher(strTeacher)
				strAnswer = self.request.get("answer")
				logic.add_answer(objStudent, objLesson, strAnswer)
				message = {
						"type": "student_choice",
						"content": {
							"student": user.username,
							"answer": strAnswer,
							},
						}
				message = json.dumps(message)
				channel.send_message(objTeacher.token, message)
			else:
				self.redirect("/check/in")
	
	def login(self):
		self.clearCookies()
		user = User()
		user.setUsername(self.request.get("username"))
		strLessonName = self.request.get("lessonName")
		user.setCurrentLesson(strLessonName)
		user.setRole("student")
		if user.studentNameNotInUse(strLessonName):
			if user.usernameIsValid():
				if strLessonName in logic.getRunningLessonList():
					user.save()
					user.setChannel()
					usercookie = UserCookie()
					usercookie.setValue(
								user.role,
								user.username,
								user.hashpassword,
								)
					usercookie.send(self)
					lessoncookie = LessonCookie()
					lessoncookie.setValue(strLessonName)
					lessoncookie.send(self)
					logic.joinLesson(user.username, user.token, strLessonName)
					return self.redirect("/s/dashboard")
				else:
					self.error = "Lesson not running now. Please type a valid lesson"
			else:
				self.error = "Username not valid"
		else:
			self.error = "Username already existing"
		self.render_page("student_login.html", error=self.error)
		
	def logout(self):
		cookie = UserCookie(self.getUserCookie())
		if cookie.value:
			user = User()
			user.username = cookie.username
			user.hashpassword = cookie.hashpassword
			if user.get():
				user.logout()
				self.clearCookies()
			else:
				MyLogs("Invalid cookie")
		else:
			MyLogs("cookie is not existing or has not value")
		self.redirect("/s/login")	

class JollyHandler(MainHandler):
	def get(self, *a):
		return self.redirect("/t/login")

class DeleteHandler(MainHandler):
	def get(self):
		ndb.delete_multi(logic.Lesson.query().fetch(keys_only=True))
		ndb.delete_multi(logic.Session.query().fetch(keys_only=True))
		ndb.delete_multi(logic.Student.query().fetch(keys_only=True))
		ndb.delete_multi(logic.Teacher.query().fetch(keys_only=True))
		return self.redirect("/t/login")

app = webapp2.WSGIApplication([
	webapp2.Route(
			r'/t/<action>',
			handler=TeacherHandler,
			name="teacher"),
	webapp2.Route(
			r'/s/<action>',
			handler=StudentHandler,
			name="student"),
	webapp2.Route(
			r'/_ah/channel/<action>/',
			handler=ConnectionHandler,
			name="connection"),
	webapp2.Route(
			r'/delete',
			handler=DeleteHandler,
			name="connection"),
	webapp2.Route(
			r'/<:[a-zA-Z0-9]*>',
			handler=JollyHandler,
			name="jolly"),
			])

dictLabelBook = {
	"TeacherLogin": {
		"username": {
			"EN": "Username",
			"IT": "Nome utente",
			},
		"password": {
			"EN": "Password",
			"IT": "Password",
			},
		"or_signup": {
			"EN": "or Signup",
			"IT": "oppure registrati",
			},
		"login": {
			"EN": "Login",
			"IT": "Entra",
			},
		},
	"TeacherSignup": {
		"username": {
			"EN": "Username",
			"IT": "Nome utente",
			},
		"password": {
			"EN": "Password",
			"IT": "Password",
			},
		"verify": {
			"EN": "Verify password",
			"IT": "Ripeti la password",
			},
		"register": {
			"EN": "Register my data",
			"IT": "Registrami",
			},
		},
	"TeacherLessonStart": {
		"lesson_name": {
			"EN": "Lesson name",
			"IT": "Nome per la lezione",
			},
		"": {
			"EN": "",
			"IT": "",
			},
		"welcome": {
			"EN": "Welcome",
			"IT": "Benvenuto",
			},
		"start": {
			"EN": "Start the lesson",
			"IT": "Inizia la lezione",
			},
		},
	}
